package local.quark.focushelper;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

/** Preserves normal key delivery; only manages Quark's full-window input focus. */
public final class FocusService extends AccessibilityService {
    private static final String TARGET = "com.quark.yun.tv";
    private static final String TAG = "QuarkFocusHelper";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private long generation;
    private int delayMs = 3000;
    private static volatile FocusService currentService;
    private AccessibilityNodeInfo lastCleared;
    private boolean clearing;
    private final Runnable delayedClear = new Runnable() {
        public void run() { clearFullWindowFocus(); }
    };

    @Override protected void onServiceConnected() {
        currentService = this;
        AccessibilityServiceInfo info = getServiceInfo();
        info.flags |= AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
            | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
            | AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;
        setServiceInfo(info);
        Log.i(TAG, "Connected; keys pass through; delay=3000ms");
        arm();
    }
    static void configurationChanged() {
        final FocusService service = currentService;
        if (service != null) {
            service.handler.post(new Runnable() { public void run() { service.arm(); } });
        }
    }
    private void arm() {
        delayMs = getSharedPreferences("agent", MODE_PRIVATE).getInt("delay_ms", 3000);
        generation++;
        clearing = false;
        handler.removeCallbacks(delayedClear);
        handler.postDelayed(delayedClear, delayMs);
    }
    private AccessibilityNodeInfo quarkRoot() {
        if (android.os.Build.VERSION.SDK_INT >= 33) clearCache();
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null || root.getPackageName() == null || !TARGET.contentEquals(root.getPackageName())) return null;
        root.refresh();
        return root;
    }
    private boolean full(AccessibilityNodeInfo n, AccessibilityNodeInfo root) {
        Rect a = new Rect(), b = new Rect();
        n.getBoundsInScreen(a); root.getBoundsInScreen(b);
        return b.width() > 0 && b.height() > 0
            && a.width() >= b.width() * 0.9 && a.height() >= b.height() * 0.9;
    }
    private AccessibilityNodeInfo fullFocusable(AccessibilityNodeInfo node,
            AccessibilityNodeInfo root, int depth) {
        if (depth > 25) return null;
        if (node.isFocusable() && node.isVisibleToUser() && full(node, root)) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                AccessibilityNodeInfo found = fullFocusable(child, root, depth + 1);
                if (found != null) return found;
            }
        }
        return null;
    }
    @Override protected boolean onKeyEvent(KeyEvent event) {
        int key = event.getKeyCode();
        if (!((key >= KeyEvent.KEYCODE_DPAD_UP && key <= KeyEvent.KEYCODE_DPAD_CENTER)
                || key == KeyEvent.KEYCODE_ENTER || key == KeyEvent.KEYCODE_NUMPAD_ENTER)) return false;
        AccessibilityNodeInfo root = quarkRoot();
        if (root == null) return false;
        arm();
        if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
            long start = android.os.SystemClock.uptimeMillis();
            AccessibilityNodeInfo focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if (focused == null) {
                AccessibilityNodeInfo candidate = lastCleared;
                if (candidate == null || !candidate.refresh() || candidate.getWindowId() != root.getWindowId()) {
                    candidate = fullFocusable(root, root, 0);
                }
                if (candidate != null) {
                    // Framework ACTION_FOCUS exits touch mode before requesting focus.
                    boolean ok = candidate.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
                    Log.i(TAG, "Restored focus=" + ok + "; elapsedMs="
                        + (android.os.SystemClock.uptimeMillis() - start));
                }
            }
            Log.i(TAG, "Pass navigation key=" + key + "; clear after " + delayMs + "ms");
        }
        return false;
    }
    private void clearFullWindowFocus() {
        final long expected = generation;
        AccessibilityNodeInfo root = quarkRoot();
        if (root == null) return;
        AccessibilityNodeInfo focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        Log.i(TAG, "Timer fired; focus=" + (focused == null ? "none" :
            (full(focused, root) ? "full" : "small")));
        if (focused == null || !full(focused, root) || !focused.isVisibleToUser()) return;
        clearing = true;
        if (!AgentConnection.setTouchMode(true)) {
            clearing = false;
            Log.i(TAG, "Touch-mode companion unavailable or foreground check failed");
            return;
        }
        verifyClear(expected, 0);
    }
    private void verifyClear(final long expected, final int attempt) {
        handler.postDelayed(new Runnable() {
            public void run() {
                if (expected != generation) { clearing = false; return; }
                AccessibilityNodeInfo current = quarkRoot();
                if (current == null) { clearing = false; return; }
                AccessibilityNodeInfo focus = current.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
                if (focus != null && full(focus, current)) {
                    lastCleared = AccessibilityNodeInfo.obtain(focus);
                    Log.i(TAG, "Delayed full-window clear=" + focus.performAction(AccessibilityNodeInfo.ACTION_CLEAR_FOCUS));
                    if (attempt < 4) { verifyClear(expected, attempt + 1); return; }
                } else Log.i(TAG, "Clear verified; focus=" + (focus == null ? "none" : "small"));
                clearing = false;
            }
        }, 35);
    }
    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        if (!clearing && event.getPackageName() != null && TARGET.contentEquals(event.getPackageName())
                && (event.getEventType() == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                    || event.getEventType() == AccessibilityEvent.TYPE_VIEW_FOCUSED)) arm();
    }
    @Override public void onInterrupt() { handler.removeCallbacksAndMessages(null); }
    @Override public void onDestroy() {
        currentService = null;
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
