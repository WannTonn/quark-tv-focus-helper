import android.os.Binder;
import android.os.Bundle;
import android.os.IBinder;
import android.os.Parcel;
import android.os.Process;
import android.os.RemoteException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

/** ADB-shell Binder companion; only changes touch mode for foreground Quark. */
public final class BinderModeAgent {
    private static final String AUTHORITY = "local.quark.focushelper.agent";
    private static final String DESCRIPTOR = "local.quark.focushelper.TouchMode";
    private static final String TARGET = "com.quark.yun.tv";
    private static final int SET_TOUCH_MODE = 1;

    private static final class ModeBinder extends Binder {
        private final Object windowManager;
        private final Method setMode;
        private final Object activityManager;
        private final Method focusedTask;
        private final Method componentPackage;
        private volatile int clientUid = -1;

        ModeBinder() throws Exception {
            windowManager = Class.forName("android.view.WindowManagerGlobal")
                .getMethod("getWindowManagerService").invoke(null);
            setMode = Class.forName("android.view.IWindowManager")
                .getMethod("setInTouchMode", boolean.class, int.class);
            activityManager = Class.forName("android.app.ActivityTaskManager")
                .getMethod("getService").invoke(null);
            focusedTask = Class.forName("android.app.IActivityTaskManager")
                .getMethod("getFocusedRootTaskInfo");
            componentPackage = Class.forName("android.content.ComponentName")
                .getMethod("getPackageName");
        }

        void trustClient(int uid) {
            if (uid < 10000) throw new SecurityException("Unexpected helper UID");
            clientUid = uid;
        }

        @Override protected boolean onTransact(int code, Parcel data, Parcel reply, int flags)
                throws RemoteException {
            if (code == INTERFACE_TRANSACTION) {
                if (reply != null) reply.writeString(DESCRIPTOR);
                return true;
            }
            if (code != SET_TOUCH_MODE) return super.onTransact(code, data, reply, flags);
            data.enforceInterface(DESCRIPTOR);
            if (clientUid < 0 || Binder.getCallingUid() != clientUid)
                throw new SecurityException("Untrusted touch-mode caller");
            if (reply == null) throw new SecurityException("Synchronous request required");
            boolean desired = data.readInt() != 0;
            boolean success = false;
            long identity = Binder.clearCallingIdentity();
            try {
                Object task = focusedTask.invoke(activityManager);
                if (task != null) {
                    Object top = task.getClass().getField("topActivity").get(task);
                    if (top != null && TARGET.equals(componentPackage.invoke(top))) {
                        int displayId = task.getClass().getField("displayId").getInt(task);
                        setMode.invoke(windowManager, desired, displayId);
                        success = true;
                    }
                }
            } catch (Exception e) {
                System.out.println("Touch-mode request failed: " + reason(e).getClass().getSimpleName());
            } finally {
                Binder.restoreCallingIdentity(identity);
            }
            reply.writeNoException();
            reply.writeInt(success ? 1 : 0);
            System.out.println("Touch-mode request accepted=" + success + "; mode=" + desired);
            return true;
        }
    }

    private static final class Publisher {
        private final Object activityManager;
        private final Method acquire;
        private final Method release;
        private final Method providerCall;
        private final Object attribution;
        private final Method currentUser;

        Publisher() throws Exception {
            Class<?> am = Class.forName("android.app.ActivityManager");
            Class<?> iam = Class.forName("android.app.IActivityManager");
            activityManager = am.getMethod("getService").invoke(null);
            acquire = iam.getMethod("getContentProviderExternal",
                String.class, int.class, IBinder.class, String.class);
            release = iam.getMethod("removeContentProviderExternalAsUser",
                String.class, IBinder.class, int.class);
            Class<?> attributionClass = Class.forName("android.content.AttributionSource");
            attribution = attributionClass.getConstructor(int.class, String.class, String.class)
                .newInstance(Process.myUid(), "com.android.shell", null);
            providerCall = Class.forName("android.content.IContentProvider").getMethod("call",
                attributionClass, String.class, String.class, String.class, Bundle.class);
            currentUser = am.getMethod("getCurrentUser");
        }

        int publish(String token, ModeBinder endpoint) throws Exception {
            int userId = (Integer) currentUser.invoke(null);
            IBinder holderToken = new Binder();
            Object provider = null;
            try {
                Object holder = acquire.invoke(activityManager, AUTHORITY, userId, holderToken, "*cmd*");
                if (holder == null) throw new IllegalStateException("Helper provider unavailable");
                provider = holder.getClass().getField("provider").get(holder);
                if (provider == null) throw new IllegalStateException("Helper provider not ready");
                Bundle extras = new Bundle();
                extras.putBinder("agent", endpoint);
                Bundle response = (Bundle) providerCall.invoke(provider, attribution,
                    AUTHORITY, "register", token, extras);
                if (response == null || !response.getBoolean("registered", false))
                    throw new SecurityException("Helper rejected registration");
                int uid = response.getInt("app_uid", -1);
                endpoint.trustClient(uid);
                return uid;
            } finally {
                if (provider != null) {
                    try { release.invoke(activityManager, AUTHORITY, holderToken, userId); }
                    catch (Exception ignored) { }
                }
            }
        }
    }

    private static Throwable reason(Throwable error) {
        while (error instanceof InvocationTargetException && error.getCause() != null)
            error = error.getCause();
        return error;
    }

    public static void main(String[] args) throws Exception {
        if (Process.myUid() != 2000) throw new SecurityException("Run with ADB shell identity");
        if (args.length != 1) throw new IllegalArgumentException("Expected local config file");
        List<String> config = Files.readAllLines(Paths.get(args[0]), StandardCharsets.UTF_8);
        if (config.isEmpty()) throw new IllegalArgumentException("Empty local config");
        String token = config.get(0).trim();
        if (!token.matches("[a-fA-F0-9]{64}")) throw new IllegalArgumentException("Invalid local token");
        ModeBinder endpoint = new ModeBinder();
        Publisher publisher = new Publisher();
        boolean registered = false;
        int publishedUid = -1;
        System.out.println("Binder touch-mode companion started; foreground Quark only.");
        // app_process starts the Binder thread pool before invoking this main method.
        // Re-publishing also repairs the connection after the helper process restarts.
        for (;;) {
            try {
                int uid = publisher.publish(token, endpoint);
                if (!registered || uid != publishedUid)
                    System.out.println("Helper Binder registered; app UID=" + uid);
                publishedUid = uid;
                registered = true;
            } catch (Exception e) {
                System.out.println("Helper registration retry: " + reason(e).getClass().getSimpleName());
                registered = false;
            }
            Thread.sleep(2000);
        }
    }
}
