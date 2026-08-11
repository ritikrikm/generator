package com.are.jdt;

import com.google.gson.Gson;
import org.eclipse.jdt.core.JavaCore;
import org.eclipse.jdt.core.compiler.IProblem;
import org.eclipse.jdt.core.dom.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

public final class JdtAnalyzerMain {
    private static final Set<String> STEP_ANNOTATIONS = Set.of("Given", "When", "Then", "And", "But");

    private JdtAnalyzerMain() {}

    public static void main(String[] args) throws Exception {
        Arguments arguments = Arguments.parse(args);
        List<Path> files = Files.readAllLines(arguments.fileList(), StandardCharsets.UTF_8).stream()
                .map(String::trim).filter(value -> !value.isEmpty()).map(Path::of)
                .map(Path::toAbsolutePath).map(Path::normalize).toList();

        Map<String, String> sources = new HashMap<>();
        Map<String, String> encodings = new HashMap<>();
        for (Path file : files) {
            String encoding = detectEncoding(file);
            encodings.put(file.toString(), encoding);
            sources.put(file.toString(), read(file, encoding));
        }

        Set<Path> sourceRoots = discoverSourceRoots(files, sources);
        List<Map<String, Object>> classes = new ArrayList<>();
        List<Map<String, Object>> diagnostics = new ArrayList<>();

        ASTParser parser = ASTParser.newParser(AST.getJLSLatest());
        parser.setKind(ASTParser.K_COMPILATION_UNIT);
        parser.setResolveBindings(true);
        parser.setBindingsRecovery(true);
        parser.setStatementsRecovery(true);
        parser.setCompilerOptions(JavaCore.getOptions());

        String[] roots = sourceRoots.stream().map(Path::toString).toArray(String[]::new);
        String[] rootEncodings = sourceRoots.stream().map(root -> "UTF-8").toArray(String[]::new);
        parser.setEnvironment(new String[0], roots, rootEncodings, true);

        String[] fileNames = files.stream().map(Path::toString).toArray(String[]::new);
        String[] fileEncodings = files.stream()
                .map(path -> encodings.getOrDefault(path.toString(), "UTF-8"))
                .toArray(String[]::new);

        parser.createASTs(fileNames, fileEncodings, new String[0], new FileASTRequestor() {
            @Override
            public void acceptAST(String sourceFilePath, CompilationUnit unit) {
                Path file = Path.of(sourceFilePath).toAbsolutePath().normalize();
                String source = sources.getOrDefault(file.toString(), "");
                analyzeCompilationUnit(file, source, unit, classes, diagnostics);
            }
        }, null);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("backend", "eclipse-jdt");
        payload.put("classes", classes);
        payload.put("diagnostics", diagnostics);
        System.out.print(new Gson().toJson(payload));
    }

    private static void analyzeCompilationUnit(Path file, String source, CompilationUnit unit,
                                                List<Map<String, Object>> classes,
                                                List<Map<String, Object>> diagnostics) {
        String packageName = unit.getPackage() == null ? ""
                : unit.getPackage().getName().getFullyQualifiedName();
        List<String> imports = new ArrayList<>();
        for (Object importObject : unit.imports()) {
            if (importObject instanceof ImportDeclaration declaration) {
                imports.add(importName(declaration));
            }
        }

        int addedProblems = 0;
        for (IProblem problem : unit.getProblems()) {
            if (!problem.isError() || addedProblems >= 10) continue;
            Map<String, Object> diagnostic = new LinkedHashMap<>();
            diagnostic.put("file", file.toString());
            diagnostic.put("message", "JDT line " + problem.getSourceLineNumber() + ": " + problem.getMessage());
            diagnostic.put("severity", "warning");
            diagnostics.add(diagnostic);
            addedProblems++;
        }

        for (Object typeObject : unit.types()) {
            if (typeObject instanceof AbstractTypeDeclaration type) {
                analyzeType(file, source, unit, packageName, imports, type, "", classes);
            }
        }
    }

    private static void analyzeType(Path file, String source, CompilationUnit unit,
                                    String packageName, List<String> imports,
                                    AbstractTypeDeclaration type, String outerName,
                                    List<Map<String, Object>> classes) {
        String simpleName = type.getName().getIdentifier();
        String nestedName = outerName.isEmpty() ? simpleName : outerName + "." + simpleName;
        ITypeBinding typeBinding = resolveTypeBinding(type);

        Map<String, Object> classInfo = new LinkedHashMap<>();
        classInfo.put("file", file.toString());
        classInfo.put("name", displayTypeName(typeBinding, packageName, nestedName));
        classInfo.put("package", packageName);
        classInfo.put("imports", imports);
        classInfo.put("line", line(unit, type.getStartPosition()));
        classInfo.put("column", column(unit, type.getStartPosition()));
        classInfo.put("bindingKey", bindingKey(typeBinding));

        List<Map<String, Object>> methods = new ArrayList<>();
        for (Object bodyObject : type.bodyDeclarations()) {
            if (bodyObject instanceof MethodDeclaration method) methods.add(analyzeMethod(file, source, unit, method));
        }
        classInfo.put("methods", methods);
        classes.add(classInfo);

        for (Object bodyObject : type.bodyDeclarations()) {
            if (bodyObject instanceof AbstractTypeDeclaration nestedType) {
                analyzeType(file, source, unit, packageName, imports, nestedType, nestedName, classes);
            }
        }
    }

    private static Map<String, Object> analyzeMethod(Path file, String source,
                                                      CompilationUnit unit,
                                                      MethodDeclaration method) {
        Map<String, Object> info = new LinkedHashMap<>();
        boolean constructor = method.isConstructor();
        IMethodBinding declarationBinding = method.resolveBinding();
        if (declarationBinding != null) declarationBinding = declarationBinding.getMethodDeclaration();

        info.put("name", method.getName().getIdentifier());
        info.put("returnType", constructor || method.getReturnType2() == null ? "" : method.getReturnType2().toString());
        info.put("parameters", method.parameters().stream().map(Object::toString).toList());
        info.put("line", line(unit, method.getStartPosition()));
        info.put("column", column(unit, method.getStartPosition()));
        info.put("endLine", line(unit, method.getStartPosition() + Math.max(0, method.getLength() - 1)));
        info.put("constructor", constructor);
        info.put("bindingKey", bindingKey(declarationBinding));
        info.put("body", nodeSource(source, method.getBody()));

        StepDefinitionData stepDefinition = stepDefinition(method, unit);
        info.put("stepDefinition", stepDefinition == null ? null : stepDefinition.asMap());

        LinkedHashSet<String> callExpressions = new LinkedHashSet<>();
        LinkedHashSet<String> resolvedCallKeys = new LinkedHashSet<>();
        LinkedHashSet<String> unresolvedCalls = new LinkedHashSet<>();
        LinkedHashSet<String> stringLiterals = new LinkedHashSet<>();

        if (method.getBody() != null) {
            method.getBody().accept(new ASTVisitor() {
                @Override public boolean visit(MethodInvocation node) {
                    String expression = (node.getExpression() == null ? "" : node.getExpression() + ".")
                            + node.getName().getIdentifier();
                    recordCall(expression, node.resolveMethodBinding(), callExpressions, resolvedCallKeys, unresolvedCalls);
                    return true;
                }
                @Override public boolean visit(SuperMethodInvocation node) {
                    recordCall("super." + node.getName().getIdentifier(), node.resolveMethodBinding(),
                            callExpressions, resolvedCallKeys, unresolvedCalls);
                    return true;
                }
                @Override public boolean visit(ClassInstanceCreation node) {
                    recordCall("new " + node.getType(), node.resolveConstructorBinding(),
                            callExpressions, resolvedCallKeys, unresolvedCalls);
                    return true;
                }
                @Override public boolean visit(ConstructorInvocation node) {
                    recordCall("this", node.resolveConstructorBinding(), callExpressions, resolvedCallKeys, unresolvedCalls);
                    return true;
                }
                @Override public boolean visit(SuperConstructorInvocation node) {
                    recordCall("super", node.resolveConstructorBinding(), callExpressions, resolvedCallKeys, unresolvedCalls);
                    return true;
                }
                @Override public boolean visit(StringLiteral node) {
                    stringLiterals.add(node.getLiteralValue());
                    return false;
                }
                @Override public boolean visit(AnonymousClassDeclaration node) { return false; }
                @Override public boolean visit(TypeDeclaration node) { return false; }
                @Override public boolean visit(EnumDeclaration node) { return false; }
                @Override public boolean visit(RecordDeclaration node) { return false; }
            });
        }

        info.put("callExpressions", new ArrayList<>(callExpressions));
        info.put("resolvedCallKeys", new ArrayList<>(resolvedCallKeys));
        info.put("unresolvedCalls", new ArrayList<>(unresolvedCalls));
        info.put("stringLiterals", new ArrayList<>(stringLiterals));
        return info;
    }

    private static void recordCall(String expression, IMethodBinding binding,
                                   Set<String> callExpressions, Set<String> resolvedCallKeys,
                                   Set<String> unresolvedCalls) {
        callExpressions.add(expression);
        if (binding == null) {
            unresolvedCalls.add(expression);
            return;
        }
        IMethodBinding declaration = binding.getMethodDeclaration();
        String key = declaration.getKey();
        if (key == null || key.isBlank()) unresolvedCalls.add(expression);
        else resolvedCallKeys.add(key);
    }

    private static StepDefinitionData stepDefinition(MethodDeclaration method, CompilationUnit unit) {
        for (Object modifier : method.modifiers()) {
            if (!(modifier instanceof Annotation annotation)) continue;
            String fullName = annotation.getTypeName().getFullyQualifiedName();
            String keyword = fullName.substring(fullName.lastIndexOf('.') + 1);
            if (!STEP_ANNOTATIONS.contains(keyword)) continue;
            Expression expression = annotationValue(annotation);
            if (expression == null) continue;
            Object constant = expression.resolveConstantExpressionValue();
            String pattern = constant instanceof String ? (String) constant
                    : expression instanceof StringLiteral literal ? literal.getLiteralValue() : null;
            if (pattern == null) continue;
            return new StepDefinitionData(keyword, pattern, line(unit, annotation.getStartPosition()),
                    column(unit, annotation.getStartPosition()));
        }
        return null;
    }

    private static Expression annotationValue(Annotation annotation) {
        if (annotation instanceof SingleMemberAnnotation single) return single.getValue();
        if (annotation instanceof NormalAnnotation normal) {
            for (Object valueObject : normal.values()) {
                if (valueObject instanceof MemberValuePair pair
                        && "value".equals(pair.getName().getIdentifier())) return pair.getValue();
            }
        }
        return null;
    }

    private static Set<Path> discoverSourceRoots(List<Path> files, Map<String, String> sources) {
        LinkedHashSet<Path> roots = new LinkedHashSet<>();
        for (Path file : files) {
            ASTParser parser = ASTParser.newParser(AST.getJLSLatest());
            parser.setKind(ASTParser.K_COMPILATION_UNIT);
            parser.setSource(sources.getOrDefault(file.toString(), "").toCharArray());
            CompilationUnit unit = (CompilationUnit) parser.createAST(null);
            String packageName = unit.getPackage() == null ? ""
                    : unit.getPackage().getName().getFullyQualifiedName();
            Path root = file.getParent();
            if (!packageName.isEmpty()) {
                String[] segments = packageName.split("\\.");
                Path candidate = root;
                boolean matches = true;
                for (int index = segments.length - 1; index >= 0; index--) {
                    if (candidate == null || candidate.getFileName() == null
                            || !candidate.getFileName().toString().equals(segments[index])) {
                        matches = false;
                        break;
                    }
                    candidate = candidate.getParent();
                }
                if (matches && candidate != null) root = candidate;
            }
            if (root != null) roots.add(root.toAbsolutePath().normalize());
        }
        return roots;
    }

    private static ITypeBinding resolveTypeBinding(AbstractTypeDeclaration type) {
        if (type instanceof TypeDeclaration value) return value.resolveBinding();
        if (type instanceof EnumDeclaration value) return value.resolveBinding();
        if (type instanceof RecordDeclaration value) return value.resolveBinding();
        if (type instanceof AnnotationTypeDeclaration value) return value.resolveBinding();
        return null;
    }

    private static String displayTypeName(ITypeBinding binding, String packageName, String fallback) {
        if (binding == null || binding.getQualifiedName().isBlank()) return fallback;
        String qualified = binding.getQualifiedName();
        String prefix = packageName.isEmpty() ? "" : packageName + ".";
        return qualified.startsWith(prefix) ? qualified.substring(prefix.length()) : qualified;
    }

    private static String bindingKey(IBinding binding) {
        return binding == null || binding.getKey() == null ? "" : binding.getKey();
    }

    private static String importName(ImportDeclaration value) {
        return value.getName().getFullyQualifiedName() + (value.isOnDemand() ? ".*" : "");
    }

    private static int line(CompilationUnit unit, int offset) {
        int value = unit.getLineNumber(offset);
        return value > 0 ? value : 1;
    }

    private static int column(CompilationUnit unit, int offset) {
        int value = unit.getColumnNumber(offset);
        return value >= 0 ? value + 1 : 1;
    }

    private static String nodeSource(String source, ASTNode node) {
        if (node == null) return "";
        int start = Math.max(0, node.getStartPosition());
        int end = Math.min(source.length(), start + Math.max(0, node.getLength()));
        return start <= end ? source.substring(start, end) : "";
    }

    private static String detectEncoding(Path file) throws IOException {
        byte[] bytes = Files.readAllBytes(file);
        try {
            StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes));
            return StandardCharsets.UTF_8.name();
        } catch (CharacterCodingException ignored) {
            return Charset.forName("windows-1252").name();
        }
    }

    private static String read(Path file, String encoding) throws IOException {
        return Files.readString(file, Charset.forName(encoding));
    }

    private record StepDefinitionData(String keyword, String pattern, int line, int column) {
        Map<String, Object> asMap() {
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("keyword", keyword); value.put("pattern", pattern);
            value.put("line", line); value.put("column", column);
            return value;
        }
    }

    private record Arguments(Path projectRoot, Path fileList) {
        static Arguments parse(String[] args) {
            Path projectRoot = null; Path fileList = null;
            for (int index = 0; index < args.length; index++) {
                if ("--project-root".equals(args[index]) && index + 1 < args.length) projectRoot = Path.of(args[++index]);
                else if ("--file-list".equals(args[index]) && index + 1 < args.length) fileList = Path.of(args[++index]);
            }
            if (projectRoot == null || fileList == null) throw new IllegalArgumentException("Usage: --project-root <path> --file-list <path>");
            return new Arguments(projectRoot.toAbsolutePath().normalize(), fileList.toAbsolutePath().normalize());
        }
    }
}
