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
