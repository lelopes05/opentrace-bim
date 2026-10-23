// SPDX-License-Identifier: GPL-3.0-or-later
//! OpenTrace BIM 0.44.0 Rust: object arrangement calculations.
//! Values are flattened (xmin,xmax,ymin,ymax,zmin,zmax) per object in metres.
//! Only primitive arrays cross the FFI boundary; Qt, geometry ownership and
//! undo/redo stay in the existing Python implementation.

use std::cmp::Ordering;

const VALUES_PER_OBJECT: usize = 6;

fn inputs<'a>(ptr: *const f64, count: usize, axis: usize, out: *mut f64) -> Option<(&'a [f64], &'a mut [f64])> {
    if ptr.is_null() || out.is_null() || axis > 2 {
        return None;
    }
    let len = count.checked_mul(VALUES_PER_OBJECT)?;
    if len > isize::MAX as usize / std::mem::size_of::<f64>() {
        return None;
    }
    // SAFETY: The Python ctypes adapter allocates exactly count*6 f64 values
    // and a separate count-element output buffer for the lifetime of this call.
    let values = unsafe { std::slice::from_raw_parts(ptr, len) };
    let output = unsafe { std::slice::from_raw_parts_mut(out, count) };
    Some((values, output))
}

fn align(values: &[f64], count: usize, axis: usize, edge: i32, result: &mut [f64]) -> i32 {
    if count < 2 || axis > 2 || !matches!(edge, 0..=2) {
        return 1;
    }
    let ix = axis * 2;
    let lo = (0..count).map(|i| values[i * 6 + ix]).fold(f64::INFINITY, f64::min);
    let hi = (0..count).map(|i| values[i * 6 + ix + 1]).fold(f64::NEG_INFINITY, f64::max);
    let target = match edge { 0 => lo, 2 => hi, _ => (lo + hi) / 2.0 };
    for (i, delta) in result.iter_mut().enumerate().take(count) {
        let a = values[i * 6 + ix];
        let b = values[i * 6 + ix + 1];
        let reference = match edge { 0 => a, 2 => b, _ => (a + b) / 2.0 };
        *delta = target - reference;
    }
    0
}

fn distribute(values: &[f64], count: usize, axis: usize, result: &mut [f64]) -> i32 {
    if count < 3 || axis > 2 {
        return 1;
    }
    let ix = axis * 2;
    let mut order: Vec<usize> = (0..count).collect();
    order.sort_by(|&a, &b| {
        values[a * 6 + ix].partial_cmp(&values[b * 6 + ix]).unwrap_or(Ordering::Equal)
            .then_with(|| values[a * 6 + ix + 1].partial_cmp(&values[b * 6 + ix + 1]).unwrap_or(Ordering::Equal))
            .then_with(|| a.cmp(&b))
    });
    let low = values[order[0] * 6 + ix];
    let high = values[order[count - 1] * 6 + ix + 1];
    let widths: Vec<f64> = order.iter().map(|&i| values[i * 6 + ix + 1] - values[i * 6 + ix]).collect();
    let sum: f64 = widths.iter().sum();
    let gap = (high - low - sum) / (count - 1) as f64;
    if gap < -1.0e-8 {
        return 2;
    }
    let mut cursor = low;
    for (&i, &width) in order.iter().zip(widths.iter()) {
        result[i] = cursor - values[i * 6 + ix];
        cursor += width + gap;
    }
    0
}

/// Alignment offsets; return 0 on success, 1 on invalid argument.
/// Edge: min=0, center=1, max=2.
#[no_mangle]
pub extern "C" fn opentrace_align(ptr: *const f64, count: usize, axis: usize, edge: i32, out: *mut f64) -> i32 {
    let Some((values, output)) = inputs(ptr, count, axis, out) else { return 1; };
    align(values, count, axis, edge, output)
}

/// Equal-clear-gap distribution; return 0 on success, 1 on invalid argument,
/// or 2 when the objects occupy more room than the selected interval.
#[no_mangle]
pub extern "C" fn opentrace_distribute(ptr: *const f64, count: usize, axis: usize, out: *mut f64) -> i32 {
    let Some((values, output)) = inputs(ptr, count, axis, out) else { return 1; };
    distribute(values, count, axis, output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alignment_by_min_center_and_max() {
        let boxes = [0.0,2.0, 0.0,1.0, 0.0,1.0, 4.0,6.0, 0.0,1.0, 0.0,1.0];
        let mut d = [0.0; 2];
        assert_eq!(align(&boxes, 2, 0, 0, &mut d), 0);
        assert_eq!(d, [0.0, -4.0]);
        assert_eq!(align(&boxes, 2, 0, 1, &mut d), 0);
        assert_eq!(d, [2.0, -2.0]);
        assert_eq!(align(&boxes, 2, 0, 2, &mut d), 0);
        assert_eq!(d, [4.0, 0.0]);
    }

    #[test]
    fn distribute_three_objects() {
        let boxes = [0.0,1.0, 0.0,1.0, 0.0,1.0,
                     2.0,3.0, 0.0,1.0, 0.0,1.0,
                     8.0,9.0, 0.0,1.0, 0.0,1.0];
        let mut d = [0.0; 3];
        assert_eq!(distribute(&boxes, 3, 0, &mut d), 0);
        assert_eq!(d, [0.0, 2.0, 0.0]);
    }

    #[test]
    fn reject_overcrowded_interval() {
        let boxes = [0.0,3.0, 0.0,1.0, 0.0,1.0,
                     1.0,4.0, 0.0,1.0, 0.0,1.0,
                     2.0,5.0, 0.0,1.0, 0.0,1.0];
        let mut d = [0.0; 3];
        assert_eq!(distribute(&boxes, 3, 0, &mut d), 2);
    }
}


// Native geometry used by walls, slabs, openings, doors, beams and profiles.
// All output memory is owned by the Python caller; no allocations cross FFI.
fn orient2(a: [f64;2], b: [f64;2], c: [f64;2]) -> f64 {
    (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
}
fn on_segment2(a: [f64;2], b: [f64;2], p: [f64;2], tol:f64) -> bool {
    orient2(a,b,p).abs() <= tol &&
    p[0] >= a[0].min(b[0])-tol && p[0] <= a[0].max(b[0])+tol &&
    p[1] >= a[1].min(b[1])-tol && p[1] <= a[1].max(b[1])+tol
}
fn intersects2(a:[f64;2], b:[f64;2], c:[f64;2], d:[f64;2], tol:f64)->bool {
    let (p,q,r,s)=(orient2(a,b,c),orient2(a,b,d),orient2(c,d,a),orient2(c,d,b));
    if ((p>tol&&q< -tol)||(p< -tol&&q>tol)) &&
       ((r>tol&&s< -tol)||(r< -tol&&s>tol)) {return true;}
    (p.abs()<=tol && on_segment2(a,b,c,tol)) ||
    (q.abs()<=tol && on_segment2(a,b,d,tol)) ||
    (r.abs()<=tol && on_segment2(c,d,a,tol)) ||
    (s.abs()<=tol && on_segment2(c,d,b,tol))
}
#[no_mangle]
pub extern "C" fn opentrace_intersects_xy(coords:*const f64, tol:f64)->i32 {
    if coords.is_null() || !tol.is_finite() {return -1;}
    let p=unsafe{std::slice::from_raw_parts(coords,8)};
    if !p.iter().all(|v|v.is_finite()) {return -1;}
    if intersects2([p[0],p[1]],[p[2],p[3]],[p[4],p[5]],[p[6],p[7]],tol) {1} else {0}
}
fn signed_area_raw(coords:&[f64])->f64 {
    let n=coords.len()/2;
    let mut area=0.0;
    for i in 0..n {
        let j=(i+1)%n;
        area+=coords[2*i]*coords[2*j+1]-coords[2*j]*coords[2*i+1];
    }
    area*0.5
}
#[no_mangle]
pub extern "C" fn opentrace_area_xy(coords:*const f64,n:usize)->f64 {
    if coords.is_null() || n<3 || n > 200_000 {return f64::NAN;}
    let vals=unsafe{std::slice::from_raw_parts(coords,n*2)};
    signed_area_raw(vals)
}
#[no_mangle]
pub extern "C" fn opentrace_point_in_polygon(x:f64,y:f64,coords:*const f64,n:usize)->i32 {
    if coords.is_null() || n<3 || n>200_000 {return -1;}
    let vals=unsafe{std::slice::from_raw_parts(coords,n*2)};
    let mut inside=false;
    let mut j=n-1;
    for i in 0..n {
        let xi=vals[2*i]; let yi=vals[2*i+1];
        let xj=vals[2*j]; let yj=vals[2*j+1];
        if (yi>y)!=(yj>y) {
            let den=yj-yi;
            let xx=(xj-xi)*(y-yi)/(if den.abs()>1.0e-10 {den} else {1.0e-10})+xi;
            if x<xx { inside=!inside; }
        }
        j=i;
    }
    if inside {1} else {0}
}
fn circum2(a:[f64;2],b:[f64;2],c:[f64;2])->Option<[f64;2]> {
    let (ax,ay,bx,by,cx,cy)=(a[0],a[1],b[0],b[1],c[0],c[1]);
    let d=2.0*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by));
    if d.abs()<1.0e-12 {return None;}
    let aa=ax*ax+ay*ay;let bb=bx*bx+by*by;let cc=cx*cx+cy*cy;
    Some([(aa*(by-cy)+bb*(cy-ay)+cc*(ay-by))/d,
          (aa*(cx-bx)+bb*(ax-cx)+cc*(bx-ax))/d])
}
fn wrap_angle(mut a:f64)->f64 {
    while a<=-std::f64::consts::PI {a+=std::f64::consts::TAU;}
    while a>std::f64::consts::PI {a-=std::f64::consts::TAU;}
    a
}
fn sample_arc(a:[f64;2],b:[f64;2],h:f64,step_deg:f64,max_seg:f64,
              max_samples:usize,min_spans:usize,opening:bool,output:&mut [f64])->i32 {
    let dx=b[0]-a[0]; let dy=b[1]-a[1]; let chord=dx.hypot(dy);
    if !h.is_finite() || !chord.is_finite() || step_deg<=0.0 || max_samples<2 {return -1;}
    if chord<=1.0e-8 || h.abs()<=1.0e-9 {
        output[..4].copy_from_slice(&[a[0],a[1],b[0],b[1]]);
        return 2;
    }
    let (cx,cy,rad)=if opening {
        let nx=-dy/chord;let ny=dx/chord;
        let radius=(chord*chord/4.0+h*h)/(2.0*h.abs());
        let offset=radius-h.abs();
        let sign=if h>0.0 {1.0} else {-1.0};
        ((a[0]+b[0])/2.0-nx*sign*offset,(a[1]+b[1])/2.0-ny*sign*offset,radius)
    } else {
        let nx=-dy/chord;let ny=dx/chord;
        let apex=[(a[0]+b[0])/2.0+nx*h,(a[1]+b[1])/2.0+ny*h];
        let Some(c)=circum2(a,apex,b) else {
            output[..4].copy_from_slice(&[a[0],a[1],b[0],b[1]]);
            return 2;
        };
        (c[0],c[1],(a[0]-c[0]).hypot(a[1]-c[1]))
    };
    let a0=(a[1]-cy).atan2(a[0]-cx);
    let a1=(b[1]-cy).atan2(b[0]-cx);
    let nx=-dy/chord; let ny=dx/chord;
    let apex=[(a[0]+b[0])/2.0+nx*h,(a[1]+b[1])/2.0+ny*h];
    let am=(apex[1]-cy).atan2(apex[0]-cx);
    let mut sweep=wrap_angle(a1-a0);
    let through=wrap_angle(am-a0);
    if sweep>=0.0 && !(0.0<=through && through<=sweep) {sweep-=std::f64::consts::TAU;}
    else if sweep<0.0 && !(sweep<=through && through<=0.0) {sweep+=std::f64::consts::TAU;}
    let ang_spans=(sweep.abs().to_degrees()/step_deg).ceil() as usize;
    let length_spans=if max_seg>0.0 {(sweep.abs()*rad/max_seg).ceil() as usize} else {0};
    let spans=if opening {ang_spans.max(min_spans)} else {ang_spans.max(length_spans).max(min_spans).min(max_samples)};
    if spans>max_samples || output.len()<(spans+1)*2 {return -2;}
    for k in 0..=spans {
        let theta=a0+sweep*(k as f64/spans as f64);
        output[2*k]=cx+rad*theta.cos();
        output[2*k+1]=cy+rad*theta.sin();
    }
    if opening {
        output[0]=a[0];output[1]=a[1];
        output[spans*2]=b[0];output[spans*2+1]=b[1];
    }
    (spans+1) as i32
}
#[no_mangle]
pub extern "C" fn opentrace_arc_xy(ax:f64,ay:f64,bx:f64,by:f64,h:f64,step_deg:f64,
                                  max_seg:f64,max_samples:usize,min_spans:usize,
                                  opening:i32,out:*mut f64)->i32 {
    if out.is_null() || max_samples>16384 || max_samples<2 {return -1;}
    let buf=unsafe{std::slice::from_raw_parts_mut(out,(max_samples+1)*2)};
    sample_arc([ax,ay],[bx,by],h,step_deg,max_seg,max_samples,min_spans,opening!=0,buf)
}
#[no_mangle]
pub extern "C" fn opentrace_vertical_beam(positions:*const f64,n:usize,length:f64,rise:f64,h:f64,out:*mut f64)->i32 {
    if positions.is_null() || out.is_null() || n>200_000 {return -1;}
    let ps=unsafe{std::slice::from_raw_parts(positions,n)};
    let dst=unsafe{std::slice::from_raw_parts_mut(out,n)};
    if length<0.001 || h.abs()<1.0e-9 {
        for (i,s) in ps.iter().enumerate() {dst[i]=if length<0.001 {0.0} else {rise*(*s/length)};}
        return 0;
    }
    let mid=[length/2.0,rise/2.0+h];
    let Some(center)=circum2([0.0,0.0],mid,[length,rise]) else {
        for (i,s) in ps.iter().enumerate() {dst[i]=rise*(*s/length);}
        return 0;
    };
    let (cx,cz)=(center[0],center[1]);
    let rad=cx.hypot(cz);
    let sign=if mid[1]>=cz {1.0} else {-1.0};
    for (i,s) in ps.iter().enumerate() {
        let under=rad*rad-(*s-cx).powi(2);
        if under< -1.0e-7 {return 2;}
        dst[i]=cz+sign*under.max(0.0).sqrt();
    }
    if n>0 {dst[0]=0.0;dst[n-1]=rise;}
    0
}
#[no_mangle]
pub extern "C" fn opentrace_prism_vertices(bounds:*const f64,pivot:*const f64,angle_deg:f64,out:*mut f64)->i32 {
    if bounds.is_null() || out.is_null() {return -1;}
    let b=unsafe{std::slice::from_raw_parts(bounds,6)};
    if !(b[1]>b[0] && b[3]>b[2] && b[5]>b[4]) {return -1;}
    let (x0,x1,y0,y1,z0,z1)=(b[0],b[1],b[2],b[3],b[4],b[5]);
    let pts=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
             (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)];
    let p=if pivot.is_null(){None}else{let v=unsafe{std::slice::from_raw_parts(pivot,2)};Some((v[0],v[1]))};
    let (sin,cos)=angle_deg.to_radians().sin_cos();
    let out=unsafe{std::slice::from_raw_parts_mut(out,24)};
    for (i,(mut x,mut y,z)) in pts.into_iter().enumerate() {
        if let Some((px,py))=p {
            let dx=x-px;let dy=y-py;
            x=px+cos*dx-sin*dy;y=py+sin*dx+cos*dy;
        }
        out[3*i]=x;out[3*i+1]=y;out[3*i+2]=z;
    }
    0
}
#[no_mangle]
pub extern "C" fn opentrace_door_grooves(count:usize,width:f64,height:f64,thickness:f64,margin:f64,offset:f64,out:*mut f64)->i32 {
    if out.is_null() || count<1 || count>12 || !width.is_finite() {return -1;}
    let dest=unsafe{std::slice::from_raw_parts_mut(out,count*4)};
    for i in 1..=count {
        let x=width*i as f64/(count+1) as f64+offset;
        let start=(i-1)*4;
        dest[start..start+4].copy_from_slice(&[x-thickness/2.0,x+thickness/2.0,margin,height-margin]);
    }
    0
}
#[cfg(test)]
mod extended_geometry_tests {
    use super::*;
    #[test] fn polygon_orientation() {
        let p=[0.0,0.0,2.0,0.0,2.0,2.0,0.0,2.0];
        assert!((signed_area_raw(&p)-4.0).abs()<1e-10);
        assert!(intersects2([0.0,0.0],[2.0,2.0],[0.0,2.0],[2.0,0.0],1e-9));
    }
    #[test] fn wall_and_slab_arcs() {
        let mut out=[0.0;514];
        let n=sample_arc([0.0,0.0],[4.0,0.0],1.0,5.0,0.2,256,4,false,&mut out);
        assert!(n>=5);
        assert!(out[0].abs()<1e-8);
        assert!((out[(n as usize-1)*2]-4.0).abs()<1e-8);
    }
    #[test] fn door_prism() {
        let b=[0.0,1.0,0.0,0.1,0.0,2.0];let mut out=[0.0;24];
        assert_eq!(opentrace_prism_vertices(b.as_ptr(),std::ptr::null(),0.0,out.as_mut_ptr()),0);
        assert_eq!(out[23],2.0);
    }
}


// OpenTrace 0.44.0 Rust: orientation of native column section rings.
// mode 0: horizontal cut; 1: plane normal to curved axis;
// mode 2: custom incline from horizontal in the bending direction.
// All profile lengths are conserved by rigid rotation; no enlargement or
// implicit contraction of the user-specified cross-section occurs.
#[no_mangle]
pub extern "C" fn opentrace_column_ring(
    profile:*const f64,n:usize,center:*const f64,tangent:*const f64,
    mode:i32,angle_deg:f64,out:*mut f64
)->i32 {
    if profile.is_null()||center.is_null()||tangent.is_null()||out.is_null()
        ||n<3||n>100_000||!matches!(mode,0..=2) {return -1;}
    let v=unsafe{std::slice::from_raw_parts(profile,2*n)};
    let c=unsafe{std::slice::from_raw_parts(center,3)};
    let t=unsafe{std::slice::from_raw_parts(tangent,3)};
    if !v.iter().chain(c).chain(t).all(|x|x.is_finite())||!angle_deg.is_finite(){return -1;}
    let dst=unsafe{std::slice::from_raw_parts_mut(out,3*n)};
    let lateral=t[0].hypot(t[1]);
    let theta=match mode {
        0=>0.0,
        1=>lateral.atan2(t[2]),
        _=>angle_deg.to_radians(),
    };
    let (s,co)=theta.sin_cos();
    let (kx,ky)=if lateral>1.0e-12 {(-t[1]/lateral,t[0]/lateral)}else{(0.0,1.0)};
    for i in 0..n {
        let x=v[2*i];let y=v[2*i+1];
        let dot=kx*x+ky*y;
        dst[3*i]=c[0]+co*x+(1.0-co)*kx*dot;
        dst[3*i+1]=c[1]+co*y+(1.0-co)*ky*dot;
        dst[3*i+2]=c[2]+s*(kx*y-ky*x);
    }
    0
}

// Advisory modelling checks. Flags are warnings, never structural approval:
// 1: sagitta > L/30; 2: middle width/diameter <80% of the wider end;
// 4: middle area <70% of wider-end area; 8: min section dimension <14cm;
// 16: min dimension <19cm; 32: section area <360cm2;
// 64: illustrative L/r >90 using L_eff = L (NOT a verified design length).
#[no_mangle]
pub extern "C" fn opentrace_column_guidance(
    height:f64,base_w:f64,base_d:f64,top_w:f64,top_d:f64,
    middle_w:f64,middle_d:f64,sagitta:f64,circular:i32
)->i32 {
    let v=[height,base_w,base_d,top_w,top_d,middle_w,middle_d,sagitta];
    if !v.iter().all(|x|x.is_finite()) || height<=0.0
       || [base_w,base_d,top_w,top_d,middle_w,middle_d].iter().any(|x|*x<=0.0)
       {return -1;}
    let mut flags=0;
    if sagitta.abs()>height/30.0+1.0e-9 {flags|=1;}
    let ratio_w=middle_w/base_w.max(top_w);
    let ratio_d=middle_d/base_d.max(top_d);
    if ratio_w.min(ratio_d)<0.8-1.0e-9 {flags|=2;}
    let factor=if circular {std::f64::consts::PI/4.0}else{1.0};
    let area=factor*middle_w*middle_d;
    let end_area=factor*(base_w*base_d).max(top_w*top_d);
    if area<0.7*end_area-1.0e-9 {flags|=4;}
    if middle_w.min(middle_d)<0.14-1.0e-9 {flags|=8;}
    if middle_w.min(middle_d)<0.19-1.0e-9 {flags|=16;}
    if area<0.036-1.0e-9 {flags|=32;}
    let r=if circular {middle_w/4.0}else{middle_w.min(middle_d)/12.0_f64.sqrt()};
    if height/r>90.0 {flags|=64;}
    flags
}

#[cfg(test)]
mod column_geometry_tests {
    use super::*;
    #[test]
    fn section_lengths_conserved_on_curved_axis() {
        let p=[-0.2,-0.15,0.2,-0.15,0.2,0.15,-0.2,0.15];
        let center=[0.1,0.2,1.5];let axis=[0.4,0.0,0.5];
        let mut out=[0.0;12];
        assert_eq!(opentrace_column_ring(p.as_ptr(),4,center.as_ptr(),axis.as_ptr(),1,0.0,out.as_mut_ptr()),0);
        for (i,j) in [(0,1),(1,2),(2,3),(3,0)] {
            let d=((out[3*i]-out[3*j]).powi(2)+(out[3*i+1]-out[3*j+1]).powi(2)+(out[3*i+2]-out[3*j+2]).powi(2)).sqrt();
            assert!((d-if i%2==0 {0.4}else{0.3}).abs()<1.0e-10);
        }
    }
    #[test]
    fn geometric_limits_are_advisory_not_approval() {
        assert_eq!(opentrace_column_guidance(3.0,0.4,0.4,0.4,0.4,0.34,0.34,0.08,0),0);
        let flags=opentrace_column_guidance(3.0,0.4,0.4,0.4,0.4,0.12,0.12,0.25,1);
        assert_eq!(flags&1,1);assert_ne!(flags&2,0);assert_ne!(flags&8,0);
        assert_eq!(opentrace_column_guidance(-1.0,0.4,0.4,0.4,0.4,0.3,0.3,0.0,0),-1);
    }
}
