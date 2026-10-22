package com.opentrace.ingetrazo.rendererlab;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.Context;
import android.content.pm.FeatureInfo;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    private GpuSurface gpuSurface;
    private int choice = 0;
    private static final String[] ENGINES = {
        "Qt QRhi + Vulkan", "wgpu / Rust", "Google Filament"
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        choice = getPreferences(MODE_PRIVATE).getInt("engine", 0);
        showMenu();
    }
    private int dp(int value) {
        return Math.round(getResources().getDisplayMetrics().density * value);
    }
    private TextView label(LinearLayout column, String message, float size) {
        TextView item = new TextView(this);
        item.setText(message);
        item.setTextSize(size);
        item.setPadding(0, dp(5), 0, dp(6));
        column.addView(item);
        return item;
    }
    private void button(LinearLayout parent, String title, View.OnClickListener click) {
        Button item = new Button(this);
        item.setText(title);
        item.setAllCaps(false);
        item.setOnClickListener(click);
        parent.addView(item);
    }
    private String capabilities() {
        ActivityManager am = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
        String gl = am != null ? am.getDeviceConfigurationInfo().getGlEsVersion() : "unknown";
        boolean vk = getPackageManager().hasSystemFeature(PackageManager.FEATURE_VULKAN_HARDWARE_VERSION);
        StringBuilder info = new StringBuilder();
        info.append("Android ").append(Build.VERSION.RELEASE)
            .append(" / API ").append(Build.VERSION.SDK_INT).append("\n")
            .append("Hardware ").append(Build.MANUFACTURER).append(" ").append(Build.MODEL).append("\n")
            .append("CPU ").append(String.join(", ", Build.SUPPORTED_ABIS)).append("\n")
            .append("OpenGL ES ").append(gl).append("\n")
            .append("Vulkan support reported: ").append(vk ? "yes" : "no");
        for (FeatureInfo feature : getPackageManager().getSystemAvailableFeatures()) {
            if (PackageManager.FEATURE_VULKAN_HARDWARE_VERSION.equals(feature.name)) {
                int v = feature.version;
                info.append(" (").append(v >>> 22).append(".")
                    .append((v >>> 12) & 0x3ff).append(")");
            }
        }
        return info.toString();
    }
    private void showMenu() {
        gpuSurface = null;
        ScrollView scroll = new ScrollView(this);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(dp(22), dp(18), dp(22), dp(26));
        scroll.addView(layout);
        label(layout, "IngeTrazo — GPU compatibility lab", 23f);
        label(layout, "Mouse e teclado Bluetooth funcionam como entradas Android. Este pacote é um diagnóstico de GPU; ainda NÃO contém o IngeTrazo nem os três renderizadores portados.", 15f);
        label(layout, capabilities(), 14f);
        label(layout, "Backends planejados", 18f);

        RadioGroup group = new RadioGroup(this);
        group.setOrientation(RadioGroup.VERTICAL);
        for (int i = 0; i < ENGINES.length; i++) {
            RadioButton item = new RadioButton(this);
            item.setText(ENGINES[i] + " — integração pendente");
            item.setId(i + 1);
            item.setPadding(0, dp(8), 0, dp(8));
            group.addView(item);
        }
        group.check(choice + 1);
        group.setOnCheckedChangeListener((g, id) -> {
            choice = id - 1;
            getPreferences(MODE_PRIVATE).edit().putInt("engine", choice).apply();
        });
        layout.addView(group);
        button(layout, "Ver estado do backend", v -> new AlertDialog.Builder(this)
            .setTitle(ENGINES[choice])
            .setMessage("PENDENTE: o backend foi selecionado, mas ainda não foi compilado nem integrado com a viewport do IngeTrazo. Esta opção não executa renderização simulada.")
            .setPositiveButton("OK", null).show());
        label(layout, "Teste real disponível", 18f);
        label(layout, "Teste independente OpenGL ES 3.0: desenha um triângulo animado por shaders na GPU do aparelho. Não representa nenhum dos três backends acima.", 14f);
        button(layout, "Executar teste OpenGL ES 3.0", v -> {
            gpuSurface = new GpuSurface(this);
            setContentView(gpuSurface);
        });
        setContentView(scroll);
    }
    @Override public void onBackPressed() {
        if (gpuSurface != null) { showMenu(); }
        else { super.onBackPressed(); }
    }
    @Override protected void onPause() {
        if (gpuSurface != null) gpuSurface.onPause();
        super.onPause();
    }
    @Override protected void onResume() {
        super.onResume();
        if (gpuSurface != null) gpuSurface.onResume();
    }
}
