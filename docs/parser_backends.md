# ARE parser backends

This branch replaces ARE's default hand-written language parsing with maintained parsers.

| File / relationship | Backend |
| --- | --- |
| `.feature` grammar | Cucumber `gherkin-official` |
| Cucumber expressions / regex StepDefs | Cucumber `cucumber-expressions` |
| `.java` syntax + method/constructor bindings | Eclipse JDT Core |
| `.properties` | `javaproperties` |
| `.json` | Python `json` |
| `.xml` | `lxml` |
| `.yaml` / `.yml` | `ruamel.yaml` |
| `.csv` | Python `csv` |
| `.toml` | Python `tomllib` |
| `.ini` / `.cfg` | Python `configparser` |

Java is analyzed once per repository through `jdt_bridge`. ARE uses JDT binding keys for method and constructor `CALLS` edges and does not guess unresolved JDT targets.

The helper JAR builds locally with Maven on the first Java scan and is reused afterward. A JDK and Maven must be available on PATH.

Parser/matcher failures are not converted into High-confidence health findings. Unresolved Cucumber matching is reported under Review.
