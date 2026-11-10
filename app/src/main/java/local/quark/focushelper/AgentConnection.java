package local.quark.focushelper;
import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import android.util.Log;

final class AgentConnection {
    private static volatile IBinder agent;
    static synchronized boolean install(final IBinder next) throws RemoteException {
        if (agent == next) return false;
        next.linkToDeath(new IBinder.DeathRecipient() {
            public void binderDied() { if (agent == next) agent = null; }
        }, 0);
        agent = next;
        Log.i("QuarkFocusHelper", "ADB Binder companion authenticated");
        return true;
    }
    static boolean setTouchMode(boolean enabled) {
        IBinder binder = agent;
        if (binder == null || !binder.isBinderAlive()) return false;
        Parcel data = Parcel.obtain(), reply = Parcel.obtain();
        try {
            data.writeInterfaceToken("local.quark.focushelper.TouchMode");
            data.writeInt(enabled ? 1 : 0);
            if (!binder.transact(1, data, reply, 0)) return false;
            reply.readException();
            boolean result = reply.readInt() != 0;
            Log.i("QuarkFocusHelper", "Binder touch-mode accepted=" + result);
            return result;
        } catch (Exception e) {
            Log.i("QuarkFocusHelper", "Binder companion failure=" + e.getClass().getSimpleName());
            return false;
        } finally { data.recycle(); reply.recycle(); }
    }
}
