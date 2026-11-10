package local.quark.focushelper;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Exported only behind android.permission.DUMP, which the ADB shell holds. */
public final class ConfigReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        String token = intent.getStringExtra("token");
        int delay = intent.getIntExtra("delay_ms", 3000);
        if (token == null || !token.matches("[A-Fa-f0-9]{64}")) return;
        if (delay < 1000 || delay > 15000) return;
        context.getSharedPreferences("agent", Context.MODE_PRIVATE).edit()
            .putString("token", token).putInt("delay_ms", delay).apply();
        FocusService.configurationChanged();
    }
}
