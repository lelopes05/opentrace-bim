package com.opentrace.ingetrazo.rendererlab;

import android.content.Context;
import android.opengl.GLES30;
import android.opengl.GLSurfaceView;
import android.os.SystemClock;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** Real GPU shader diagnostic; deliberately independent of the proposed backends. */
public class GpuSurface extends GLSurfaceView implements GLSurfaceView.Renderer {
    private static final String VERTEX =
        "#version 300 es\n" +
        "layout(location=0) in vec2 pos;\n" +
        "uniform float angle;\n" +
        "void main(){float c=cos(angle),s=sin(angle);" +
        "gl_Position=vec4(c*pos.x-s*pos.y,s*pos.x+c*pos.y,0.0,1.0);}\n";
    private static final String FRAGMENT =
        "#version 300 es\n" +
        "precision mediump float;\n" +
        "out vec4 color;\n" +
        "void main(){color=vec4(0.20,0.84,0.60,1.0);}\n";
    private int program, vertices, angleUniform;
    private long start;
    public GpuSurface(Context ctx) {
        super(ctx);
        setEGLContextClientVersion(3);
        setRenderer(this);
        setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);
    }
    private int shader(int type, String source) {
        int sh = GLES30.glCreateShader(type);
        GLES30.glShaderSource(sh, source);
        GLES30.glCompileShader(sh);
        int[] status = new int[1];
        GLES30.glGetShaderiv(sh, GLES30.GL_COMPILE_STATUS, status, 0);
        if (status[0] == 0) {
            throw new IllegalStateException("Shader: " + GLES30.glGetShaderInfoLog(sh));
        }
        return sh;
    }
    @Override public void onSurfaceCreated(GL10 gl, EGLConfig cfg) {
        int vs = shader(GLES30.GL_VERTEX_SHADER, VERTEX);
        int fs = shader(GLES30.GL_FRAGMENT_SHADER, FRAGMENT);
        program = GLES30.glCreateProgram();
        GLES30.glAttachShader(program, vs);
        GLES30.glAttachShader(program, fs);
        GLES30.glLinkProgram(program);
        int[] linked = new int[1];
        GLES30.glGetProgramiv(program, GLES30.GL_LINK_STATUS, linked, 0);
        if (linked[0] == 0) throw new IllegalStateException(GLES30.glGetProgramInfoLog(program));
        GLES30.glDeleteShader(vs);
        GLES30.glDeleteShader(fs);
        angleUniform = GLES30.glGetUniformLocation(program, "angle");
        float[] xy = {0f, .62f, -.55f, -.48f, .55f, -.48f};
        FloatBuffer fb = ByteBuffer.allocateDirect(xy.length * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer();
        fb.put(xy).position(0);
        int[] ids = new int[1];
        GLES30.glGenBuffers(1, ids, 0);
        vertices = ids[0];
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, vertices);
        GLES30.glBufferData(GLES30.GL_ARRAY_BUFFER, xy.length * 4, fb, GLES30.GL_STATIC_DRAW);
        start = SystemClock.uptimeMillis();
    }
    @Override public void onSurfaceChanged(GL10 gl, int width, int height) {
        GLES30.glViewport(0, 0, width, height);
    }
    @Override public void onDrawFrame(GL10 gl) {
        GLES30.glClearColor(.075f, .09f, .12f, 1f);
        GLES30.glClear(GLES30.GL_COLOR_BUFFER_BIT);
        GLES30.glUseProgram(program);
        GLES30.glUniform1f(angleUniform, (SystemClock.uptimeMillis() - start) / 1250f);
        GLES30.glBindBuffer(GLES30.GL_ARRAY_BUFFER, vertices);
        GLES30.glEnableVertexAttribArray(0);
        GLES30.glVertexAttribPointer(0, 2, GLES30.GL_FLOAT, false, 0, 0);
        GLES30.glDrawArrays(GLES30.GL_TRIANGLES, 0, 3);
        GLES30.glDisableVertexAttribArray(0);
    }
}
