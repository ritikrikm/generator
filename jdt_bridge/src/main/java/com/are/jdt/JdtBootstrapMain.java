package com.are.jdt;

import org.eclipse.jdt.core.JavaCore;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.SortedSet;

/**
 * Selects a Java source level without hard-coding a release number, then delegates to the
 * real analyzer. A declared project level is preserved when the bundled Eclipse compiler
 * supports it. When the project has no declaration, the latest source level fully supported
 * by the bundled JDT compiler is used instead of JDT's historical default.
 */
public final class JdtBootstrapMain {
    private static final String SOURCE_LEVEL_FLAG = "--source-level";

    private JdtBootstrapMain() {}

    public static void main(String[] args) throws Exception {
        List<String> forwarded = new ArrayList<>(Arrays.asList(args));
        SortedSet<String> supported = JavaCore.getAllJavaSourceVersionsSupportedByCompiler();
        if (supported.isEmpty()) {
            throw new IllegalStateException("Bundled Eclipse JDT did not report any supported Java source levels.");
        }

        int flagIndex = forwarded.indexOf(SOURCE_LEVEL_FLAG);
        String requested = null;
        if (flagIndex >= 0) {
            if (flagIndex + 1 >= forwarded.size()) {
                throw new IllegalArgumentException(SOURCE_LEVEL_FLAG + " requires a Java version value.");
            }
            requested = normalizeSourceLevel(forwarded.get(flagIndex + 1));
        }

        String effective;
        if (requested == null) {
            effective = supported.last();
            forwarded.add(SOURCE_LEVEL_FLAG);
            forwarded.add(effective);
            System.err.println(
                    "[ARE:JDT] No project Java source level declared; using latest fully supported JDT level "
                            + effective + ".");
        } else if (!JavaCore.isJavaSourceVersionSupportedByCompiler(requested)) {
            throw new IllegalArgumentException(
                    "Project requests Java source level " + requested
                            + " but bundled Eclipse JDT fully supports " + supported
                            + ". Upgrade the ARE JDT dependency instead of analyzing with a downgraded language level.");
        } else {
            effective = requested;
            forwarded.set(flagIndex + 1, effective);
            System.err.println("[ARE:JDT] Using project Java source level " + effective + ".");
        }

        JdtAnalyzerMain.main(forwarded.toArray(String[]::new));
    }

    private static String normalizeSourceLevel(String value) {
        if (value == null) return null;
        String clean = value.trim();
        if (clean.isEmpty()) return null;

        if (clean.startsWith("1.")) {
            String remainder = clean.substring(2);
            int dot = remainder.indexOf('.');
            if (dot >= 0) remainder = remainder.substring(0, dot);
            try {
                int major = Integer.parseInt(remainder);
                return "1." + major;
            } catch (NumberFormatException ignored) {
                return clean;
            }
        }

        int delimiter = clean.indexOf('.');
        if (delimiter < 0) delimiter = clean.indexOf('-');
        String majorText = delimiter >= 0 ? clean.substring(0, delimiter) : clean;
        try {
            int major = Integer.parseInt(majorText);
            return major <= 8 ? "1." + major : Integer.toString(major);
        } catch (NumberFormatException ignored) {
            return clean;
        }
    }
}
