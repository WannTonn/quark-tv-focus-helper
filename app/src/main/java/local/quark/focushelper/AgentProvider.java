package local.quark.focushelper;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.IBinder;

public final class AgentProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }
    @Override public Bundle call(String method, String token, Bundle extras) {
        if (Binder.getCallingUid() != 2000) throw new SecurityException("ADB shell only");
        String expected = getContext().getSharedPreferences("agent", 0).getString("token", "");
        if (!"register".equals(method) || expected.length() != 64 || !expected.equals(token))
            throw new SecurityException("Invalid local registration");
        IBinder agent = extras == null ? null : extras.getBinder("agent");
        if (agent == null) throw new IllegalArgumentException("Missing agent");
        try { if (AgentConnection.install(agent)) FocusService.configurationChanged(); }
        catch (Exception e) { throw new IllegalStateException("Agent is not alive", e); }
        Bundle result = new Bundle();
        result.putBoolean("registered", true);
        result.putInt("app_uid", android.os.Process.myUid());
        return result;
    }
    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { throw new UnsupportedOperationException(); }
    @Override public String getType(Uri u) { return null; }
    @Override public Uri insert(Uri u, ContentValues v) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri u, String s, String[] a) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
}
