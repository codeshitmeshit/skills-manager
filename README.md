# cosh-skills

中文文档: [README-zh.md](README-zh.md)

`cosh-skills` is a command line tool for managing a local skill repository and syncing skills into supported CLI tools.

First-version supported targets:

- `codex`
- `claude`
- `qwen`

The tool expects you to clone the skill repository yourself. It updates that local git repository and syncs valid skills from:

```text
{repo_path}/skills/{skill-name}/SKILL.md
```

into the configured target CLI skills directory.

## Install

Run the local install script without arguments:

```bash
scripts/install.sh
```

The script installs the Python package and dependencies with editable mode, then writes a wrapper script at `~/.local/bin/cosh-skills`. The wrapper changes into this repository before running the Python module entry point, so it works from any current directory. The install script does not ask for business parameters such as `repo_path`, `cli`, or `skills_path`.

Do not alias `cosh-skills` to `python3 -m internal.cli`; that module command only works when the repository is on `PYTHONPATH`. If your shell still reports an alias, remove it from `~/.zshrc` or `~/.bashrc`. If your shell cannot find `cosh-skills`, make sure `~/.local/bin` is on `PATH`.

### Local Shell Setup

For zsh, keep this line in `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Do not add a `cosh-skills` alias. If you previously added this line, remove it:

```bash
alias cosh-skills='python3 -m internal.cli'
```

Reload your shell config and confirm the command source:

```bash
source ~/.zshrc
unalias cosh-skills 2>/dev/null || true
which cosh-skills
```

Expected output:

```text
/home/wo/.local/bin/cosh-skills
```

Verify:

```bash
cosh-skills --help
```

Initialize the Codex startup hook:

```bash
cosh-skills init --cli codex
```

This writes `~/.codex/hooks.json` and uses the current Python interpreter module entry point instead of relying on a shell alias or user `PATH` inside the Codex hook environment. It also writes the current skill repository path and sets `cli.codex.skills_path` to `~/.codex/skills` when that value is not already configured.

To make the startup hook continue syncing when the local skill repository is ahead of the remote, initialize it with:

```bash
cosh-skills init --cli codex --force
```

Codex requires new or changed non-managed hooks to be reviewed and trusted before they run. After `cosh-skills init --cli codex`, use `/hooks` in Codex to review and trust the hook.

Initialize the Qwen startup hook:

```bash
cosh-skills init --cli qwen
```

## Basic Usage

Set the local skill repository path:

```bash
cosh-skills config set repo_path /path/to/cosh-skills
```

Set the target skills path:

```bash
cosh-skills config set cli.codex.skills_path ~/.codex/skills
cosh-skills config set cli.claude.skills_path ~/.claude/skills
cosh-skills config set cli.qwen.skills_path ~/.qwen/skills
```

Optionally set install mode. First version supports `auto` and `copy`; `cli` and `link` are accepted in config but not implemented for update.

```bash
cosh-skills config set cli.codex.install_mode copy
cosh-skills config set cli.claude.install_mode auto
cosh-skills config set cli.qwen.install_mode auto
```

Show config:

```bash
cosh-skills config get
```

Update skills:

```bash
cosh-skills update --cli codex
cosh-skills update --cli claude
cosh-skills update --cli qwen
```

First use can also provide `repo_path` inline:

```bash
cosh-skills update --cli codex --repo-path /path/to/cosh-skills
```

Back up same-name target skills before overwrite:

```bash
cosh-skills update --cli codex --backup
```

Run optional CLI recognition verification:

```bash
cosh-skills update --cli codex --verify
```

Make CLI recognition verification failure block the update:

```bash
cosh-skills update --cli codex --strict-verify
```

Use local commits when the local skill repository is ahead of the remote:

```bash
cosh-skills update --cli codex --force
```

This does not overwrite uncommitted changes and does not push to the remote repository.

## First-Version Limits

This version intentionally does not support:

- cloning the skill repository
- `--cli all`
- `--branch`
- syncing only one skill
- include or exclude filters
- official CLI installer mode
- link mode
- automatic stash
- force overwriting uncommitted local git changes
- installing under a `cosh/` subdirectory

## Development

Run the test suite with:

```bash
python3 -m unittest discover -s tests
```

Run the CLI directly during development:

```bash
PYTHONPATH=/path/to/cosh-skills python3 -m internal.cli --help
```

Run the install script syntax check:

```bash
bash -n scripts/install.sh
```

Current implementation status is tracked in `docs/development-plan.md`.
