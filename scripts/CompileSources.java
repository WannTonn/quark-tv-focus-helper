import java.util.*;
import javax.tools.ToolProvider;
public class CompileSources {
    public static void main(String[] args) {
        List<String> opts = new ArrayList<String>(Arrays.asList("--release", "8", "-Xlint:-options",
            "-classpath", args[0], "-d", args[1]));
        opts.addAll(Arrays.asList(args).subList(2, args.length));
        if (ToolProvider.getSystemJavaCompiler().run(null, System.out, System.err,
                opts.toArray(new String[0])) != 0) throw new IllegalStateException("Compile failed");
    }
}
