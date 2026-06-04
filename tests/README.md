# Test Isolation

Tests must not read or write a developer's real home directory, CLI skills directories, or external skill repositories.

Use temporary directories for:

- config home
- source skill repositories
- target CLI skills directories
- backup directories

The phase 0 suite uses only standard library `unittest` so it can run before project dependencies are installed.
