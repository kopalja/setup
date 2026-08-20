#!/usr/bin/env bash
set -u

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REAL_VIM="$(command -v vim)"
REAL_ZSH="$(command -v zsh)"
REAL_TMUX="$(command -v tmux)"
failures=0

fail() {
  printf 'not ok - %s\n' "$1" >&2
  failures=$((failures + 1))
}

pass() {
  printf 'ok - %s\n' "$1"
}

assert_contains() {
  local output="$1"
  local expected="$2"
  local message="$3"

  if [[ "$output" != *"$expected"* ]]; then
    fail "$message (missing: $expected)"
    return 1
  fi
}

assert_not_contains() {
  local output="$1"
  local unexpected="$2"
  local message="$3"

  if [[ "$output" == *"$unexpected"* ]]; then
    fail "$message (unexpected: $unexpected)"
    return 1
  fi
}

write_fake_command() {
  local path="$1"
  local body="$2"

  printf '#!/usr/bin/env bash\n%s\n' "$body" >"$path"
  chmod +x "$path"
}

make_fake_commands() {
  local fake_bin="$1"

  mkdir -p "$fake_bin"
  write_fake_command "$fake_bin/curl" '
printf "curl %s\\n" "$*" >>"$SETUP_TEST_LOG"
case "$*" in
  *ohmyzsh*)
    mkdir -p "$HOME/.oh-my-zsh/.git" "$HOME/.oh-my-zsh/tools"
    : >"$HOME/.oh-my-zsh/oh-my-zsh.sh"
    printf "%s\\n" "#!/usr/bin/env bash" "echo omz-upgrade >>$SETUP_TEST_LOG" >"$HOME/.oh-my-zsh/tools/upgrade.sh"
    chmod +x "$HOME/.oh-my-zsh/tools/upgrade.sh"
    printf "%s\\n" ":"
    ;;
  *)
    if [[ "${1:-}" == -fLo ]]; then
      mkdir -p "$(dirname -- "$2")"
      printf "function! plug#begin\\n" >"$2"
      if [[ "$*" == *"junegunn/vim-plug"* && -n "${SETUP_TEST_FAIL_VIM_PLUG:-}" ]]; then
        exit 1
      fi
    fi
    ;;
esac'
  write_fake_command "$fake_bin/git" '
printf "git %s\\n" "$*" >>"$SETUP_TEST_LOG"
if [[ "$*" == *"status --porcelain"* && -n "${SETUP_TEST_GIT_DIRTY:-}" ]]; then
  printf " M locally-modified-file\\n"
  exit 0
fi
if [[ "$*" == *"merge-base --is-ancestor"* && -n "${SETUP_TEST_GIT_DIVERGED:-}" ]]; then
  exit 1
fi
if [[ "${1:-}" == clone ]]; then
  destination="${@: -1}"
  mkdir -p "$destination/.git"
fi'
  write_fake_command "$fake_bin/vim" '
printf "vim %s\\n" "$*" >>"$SETUP_TEST_LOG"
if [[ "$*" == *"PlugInstall"* || "$*" == *"PlugUpdate"* ]]; then
  mkdir -p "$HOME/.vim/plugged/gruvbox/.git" "$HOME/.vim/plugged/vim-oscyank/.git"
fi'
  write_fake_command "$fake_bin/zsh" 'exit 0'
  write_fake_command "$fake_bin/tmux" 'exit 0'
  write_fake_command "$fake_bin/chsh" '
printf "chsh %s\\n" "$*" >>"$SETUP_TEST_LOG"'
}

setup_fixture() {
  TEST_SANDBOX="$(mktemp -d)"
  TEST_FAKE_BIN="$TEST_SANDBOX/bin"
  TEST_HOME="$TEST_SANDBOX/home"
  TEST_LOG="$TEST_SANDBOX/commands.log"
  mkdir -p "$TEST_HOME"
  : >"$TEST_LOG"
  make_fake_commands "$TEST_FAKE_BIN"
}

cleanup_fixture() {
  rm -rf "$TEST_SANDBOX"
}

run_setup() {
  HOME="$TEST_HOME" \
    PATH="$TEST_FAKE_BIN:/usr/bin:/bin" \
    SETUP_TEST_LOG="$TEST_LOG" \
    SETUP_TEST_GIT_DIRTY="${SETUP_TEST_GIT_DIRTY:-}" \
    SETUP_TEST_GIT_DIVERGED="${SETUP_TEST_GIT_DIVERGED:-}" \
    SETUP_TEST_FAIL_SOURCE="${SETUP_TEST_FAIL_SOURCE:-}" \
    SETUP_TEST_FAIL_VIM_PLUG="${SETUP_TEST_FAIL_VIM_PLUG:-}" \
    SETUP_AUTHORIZED_KEY="${SETUP_AUTHORIZED_KEY:-}" \
    SHELL=/bin/bash \
    /bin/bash "$REPO_DIR/init.sh" "$@"
}

make_failing_copy_command() {
  local fake_bin="$1"

  write_fake_command "$fake_bin/cp" '
source_path="${@: -2:1}"
target_path="${@: -1}"
if [[ "$source_path" == "$SETUP_TEST_FAIL_SOURCE" ]]; then
  printf "partial write\\n" >"$target_path"
  exit 1
fi
exec /bin/cp "$@"'
}

test_reports_all_missing_prerequisites() {
  local sandbox fake_bin output status
  sandbox="$(mktemp -d)"
  fake_bin="$sandbox/bin"
  mkdir -p "$fake_bin"
  ln -s "$(command -v curl)" "$fake_bin/curl"
  ln -s "$(command -v git)" "$fake_bin/git"

  output="$(HOME="$sandbox/home" PATH="$fake_bin" /bin/bash "$REPO_DIR/init.sh" 2>&1)"
  status=$?

  if ((status == 0)); then
    fail "missing prerequisites stop setup"
  elif assert_contains "$output" "zsh" "reports missing zsh" &&
    assert_contains "$output" "vim" "reports missing vim" &&
    assert_contains "$output" "tmux" "reports missing tmux" &&
    assert_not_contains "$output" "missing required command: curl" "does not report available curl" &&
    assert_not_contains "$output" "missing required command: git" "does not report available git"; then
    pass "reports every missing prerequisite before exiting"
  fi

  rm -rf "$sandbox"
}

test_ordinary_setup_run_acquires_only_missing_dependencies() {
  local output status first_log second_log
  setup_fixture

  output="$(run_setup 2>&1)"
  status=$?
  first_log="$(<"$TEST_LOG")"

  if ((status != 0)); then
    fail "fresh setup succeeds ($output)"
  elif ! assert_contains "$first_log" "ohmyzsh" "installs missing Oh My Zsh"; then
    :
  elif ! assert_contains "$first_log" "zsh-autosuggestions" "installs missing Zsh plugin"; then
    :
  elif ! assert_not_contains "$first_log" "powerlevel10k" "does not install Powerlevel10k"; then
    :
  elif [[ ! -f "$TEST_HOME/.vim/autoload/plug.vim" ]]; then
    fail "installs vim-plug during setup"
  else
    : >"$TEST_LOG"
    output="$(run_setup 2>&1)"
    status=$?
    second_log="$(<"$TEST_LOG")"

    if ((status != 0)); then
      fail "ordinary Setup rerun succeeds ($output)"
    elif assert_not_contains "$second_log" "git -C" "ordinary Setup rerun does not update Git dependencies" &&
      assert_not_contains "$second_log" "PlugUpdate" "ordinary Setup rerun does not update Vim plugins" &&
      assert_not_contains "$second_log" "PlugUpgrade" "ordinary Setup rerun does not update vim-plug"; then
      pass "ordinary Setup run acquires missing dependencies without updating existing ones"
    fi
  fi

  cleanup_fixture
}

test_update_run_refreshes_clean_dependencies() {
  local output status update_log
  setup_fixture

  run_setup >/dev/null 2>&1
  : >"$TEST_LOG"

  output="$(run_setup --update 2>&1)"
  status=$?
  update_log="$(<"$TEST_LOG")"

  if ((status != 0)); then
    fail "Update run succeeds for clean dependencies ($output)"
  elif assert_contains "$update_log" "omz-upgrade" "updates Oh My Zsh" &&
    assert_contains "$update_log" "pull --ff-only" "fast-forwards Git dependencies" &&
    assert_contains "$update_log" "PlugUpgrade" "updates vim-plug" &&
    assert_contains "$update_log" "PlugUpdate --sync" "updates Vim plugins"; then
    pass "Update run refreshes clean dependencies"
  fi

  cleanup_fixture
}

test_update_run_rejects_modified_dependencies() {
  local output status update_log
  setup_fixture

  run_setup >/dev/null 2>&1
  : >"$TEST_LOG"

  output="$(SETUP_TEST_GIT_DIRTY=1 run_setup --update 2>&1)"
  status=$?
  update_log="$(<"$TEST_LOG")"

  if ((status == 0)); then
    fail "Update run rejects modified dependencies"
  elif assert_contains "$output" "local changes" "explains why update stopped" &&
    assert_not_contains "$update_log" "pull --ff-only" "does not overwrite modified dependencies"; then
    pass "Update run preserves modified dependency checkouts"
  fi

  cleanup_fixture
}

test_update_run_rejects_diverged_dependencies() {
  local output status update_log
  setup_fixture

  run_setup >/dev/null 2>&1
  : >"$TEST_LOG"

  output="$(SETUP_TEST_GIT_DIVERGED=1 run_setup --update 2>&1)"
  status=$?
  update_log="$(<"$TEST_LOG")"

  if ((status == 0)); then
    fail "Update run rejects diverged dependencies"
  elif assert_contains "$output" "has diverged" "explains why diverged update stopped" &&
    assert_not_contains "$update_log" "omz-upgrade" "does not run an unsafe upstream updater" &&
    assert_not_contains "$update_log" "pull --ff-only" "does not pull a diverged dependency"; then
    pass "Update run preserves diverged dependency checkouts"
  fi

  cleanup_fixture
}

test_unchanged_configurations_are_untouched() {
  local output status
  setup_fixture

  run_setup >/dev/null 2>&1
  output="$(run_setup 2>&1)"
  status=$?

  if ((status != 0)); then
    fail "unchanged rerun succeeds ($output)"
  elif [[ -e "$TEST_HOME/.setup-backups" ]]; then
    fail "unchanged configurations create no backup directory"
  elif assert_contains "$output" "Unchanged $TEST_HOME/.zshrc" "reports unchanged Zsh configuration" &&
    assert_contains "$output" "Unchanged $TEST_HOME/.vimrc" "reports unchanged Vim configuration" &&
    assert_contains "$output" "Unchanged $TEST_HOME/.tmux.conf" "reports unchanged tmux configuration"; then
    pass "ordinary Setup rerun leaves unchanged configurations untouched"
  fi

  cleanup_fixture
}

test_failed_copy_preserves_existing_configuration() {
  local output status backup_path
  setup_fixture

  run_setup >/dev/null 2>&1
  printf 'original user configuration\n' >"$TEST_HOME/.zshrc"
  make_failing_copy_command "$TEST_FAKE_BIN"

  output="$(SETUP_TEST_FAIL_SOURCE="$REPO_DIR/zshrc" run_setup 2>&1)"
  status=$?
  backup_path="$(compgen -G "$TEST_HOME/.setup-backups/*/.zshrc" | head -n 1)"

  if ((status == 0)); then
    fail "copy failure stops setup"
  elif [[ "$(<"$TEST_HOME/.zshrc")" != "original user configuration" ]]; then
    fail "copy failure leaves existing configuration intact"
  elif [[ -z "$backup_path" || "$(<"$backup_path")" != "original user configuration" ]]; then
    fail "copy failure preserves the existing configuration in a backup"
  elif compgen -G "$TEST_HOME/.zshrc.tmp.*" >/dev/null; then
    fail "copy failure removes temporary files"
  else
    pass "failed atomic copy preserves the existing configuration"
  fi

  cleanup_fixture
}

test_runtime_startup_has_no_dependency_side_effects() {
  local output status vim_config zsh_config
  setup_fixture

  output="$(run_setup 2>&1)"
  status=$?
  vim_config="$(<"$TEST_HOME/.vimrc")"
  zsh_config="$(<"$TEST_HOME/.zshrc")"

  if ((status != 0)); then
    fail "setup succeeds before runtime configuration check ($output)"
  elif ! assert_not_contains "$vim_config" "curl" "Vim startup does not download dependencies"; then
    :
  elif ! assert_not_contains "$vim_config" "PlugInstall" "Vim startup does not install dependencies"; then
    :
  elif ! assert_not_contains "$vim_config" "nvim" "Vim configuration has no Neovim behavior"; then
    :
  elif ! assert_contains "$zsh_config" "zstyle ':omz:update' mode disabled" "Zsh startup disables Oh My Zsh updates"; then
    :
  elif assert_not_contains "$zsh_config" "powerlevel10k" "Zsh configuration does not use Powerlevel10k"; then
    pass "runtime startup has no dependency installation or update effects"
  fi

  cleanup_fixture
}

test_installed_vim_configuration_parses() {
  local output status
  setup_fixture

  run_setup >/dev/null 2>&1
  {
    printf '%s\n' 'function! plug#begin(...) abort'
    printf '%s\n' '  command! -nargs=* Plug'
    printf '%s\n' 'endfunction'
    printf '%s\n' 'function! plug#end() abort'
    printf '%s\n' 'endfunction'
  } >"$TEST_HOME/.vim/autoload/plug.vim"

  output="$(HOME="$TEST_HOME" "$REAL_VIM" -Nu "$TEST_HOME/.vimrc" -n -es -i NONE -c 'qa' 2>&1)"
  status=$?

  if ((status != 0)); then
    fail "installed Vim configuration parses ($output)"
  else
    pass "installed Vim configuration parses"
  fi

  cleanup_fixture
}

test_installed_shell_configurations_parse() {
  local output zsh_status tmux_status socket_name
  setup_fixture
  socket_name="setup-test-$$-$RANDOM"

  run_setup >/dev/null 2>&1

  output="$(HOME="$TEST_HOME" "$REAL_ZSH" -n "$TEST_HOME/.zshrc" 2>&1)"
  zsh_status=$?
  "$REAL_TMUX" -L "$socket_name" -f /dev/null new-session -d
  output+="$("$REAL_TMUX" -L "$socket_name" source-file "$TEST_HOME/.tmux.conf" 2>&1)"
  tmux_status=$?
  "$REAL_TMUX" -L "$socket_name" kill-server >/dev/null 2>&1 || true

  if ((zsh_status != 0)); then
    fail "installed Zsh configuration parses ($output)"
  elif ((tmux_status != 0)); then
    fail "installed tmux configuration parses ($output)"
  else
    pass "installed Zsh and tmux configurations parse"
  fi

  cleanup_fixture
}

test_access_key_is_added_once_without_removing_existing_keys() {
  local output status
  setup_fixture
  mkdir -p "$TEST_HOME/.ssh"
  printf 'existing-key\n' >"$TEST_HOME/.ssh/authorized_keys"

  SETUP_AUTHORIZED_KEY="new-key" run_setup >/dev/null 2>&1
  output="$(SETUP_AUTHORIZED_KEY="new-key" run_setup 2>&1)"
  status=$?

  if ((status != 0)); then
    fail "Access-key rerun succeeds ($output)"
  elif ! grep -Fxq "existing-key" "$TEST_HOME/.ssh/authorized_keys"; then
    fail "preserves existing Access keys"
  elif [[ "$(grep -Fxc "new-key" "$TEST_HOME/.ssh/authorized_keys")" != 1 ]]; then
    fail "adds the configured Access key exactly once"
  else
    pass "Access-key setup preserves existing keys and avoids duplicates"
  fi

  cleanup_fixture
}

test_ordinary_setup_run_recovers_incomplete_dependencies() {
  local output status
  setup_fixture
  mkdir -p \
    "$TEST_HOME/.oh-my-zsh/custom/plugins/zsh-autosuggestions" \
    "$TEST_HOME/.vim/autoload"
  printf 'partial Oh My Zsh\n' >"$TEST_HOME/.oh-my-zsh/partial"
  printf 'partial Zsh plugin\n' >"$TEST_HOME/.oh-my-zsh/custom/plugins/zsh-autosuggestions/partial"
  : >"$TEST_HOME/.vim/autoload/plug.vim"

  output="$(run_setup 2>&1)"
  status=$?

  if ((status != 0)); then
    fail "ordinary Setup run recovers incomplete dependencies ($output)"
  elif [[ ! -d "$TEST_HOME/.oh-my-zsh/.git" ]]; then
    fail "reinstalls incomplete Oh My Zsh"
  elif [[ ! -d "$TEST_HOME/.oh-my-zsh/custom/plugins/zsh-autosuggestions/.git" ]]; then
    fail "reinstalls incomplete Zsh plugin"
  elif ! grep -Fq "plug#begin" "$TEST_HOME/.vim/autoload/plug.vim"; then
    fail "reinstalls incomplete vim-plug"
  elif ! compgen -G "$TEST_HOME/.setup-backups/*/.oh-my-zsh" >/dev/null; then
    fail "preserves incomplete Oh My Zsh before reinstalling"
  else
    pass "ordinary Setup run recovers incomplete dependencies"
  fi

  cleanup_fixture
}

test_ordinary_setup_run_recovers_incomplete_vim_plugins() {
  local output status
  setup_fixture
  mkdir -p \
    "$TEST_HOME/.vim/plugged/gruvbox" \
    "$TEST_HOME/.vim/plugged/vim-oscyank"
  printf 'partial plugin\n' >"$TEST_HOME/.vim/plugged/gruvbox/partial"
  printf 'partial plugin\n' >"$TEST_HOME/.vim/plugged/vim-oscyank/partial"

  output="$(run_setup 2>&1)"
  status=$?

  if ((status != 0)); then
    fail "ordinary Setup run recovers incomplete Vim plugins ($output)"
  elif [[ ! -d "$TEST_HOME/.vim/plugged/gruvbox/.git" ]]; then
    fail "reinstalls incomplete Gruvbox plugin"
  elif [[ ! -d "$TEST_HOME/.vim/plugged/vim-oscyank/.git" ]]; then
    fail "reinstalls incomplete vim-oscyank plugin"
  elif ! compgen -G "$TEST_HOME/.setup-backups/*/gruvbox" >/dev/null; then
    fail "preserves incomplete Vim plugins before reinstalling"
  else
    pass "ordinary Setup run recovers incomplete Vim plugins"
  fi

  cleanup_fixture
}

test_failed_vim_plug_download_leaves_no_partial_installation() {
  local output status
  setup_fixture
  mkdir -p "$TEST_HOME/.vim/autoload"
  : >"$TEST_HOME/.vim/autoload/plug.vim"

  output="$(SETUP_TEST_FAIL_VIM_PLUG=1 run_setup 2>&1)"
  status=$?

  if ((status == 0)); then
    fail "failed vim-plug download stops setup"
  elif [[ -e "$TEST_HOME/.vim/autoload/plug.vim" ]]; then
    fail "failed vim-plug download leaves no partial installation"
  elif compgen -G "$TEST_HOME/.vim/autoload/plug.vim.tmp.*" >/dev/null; then
    fail "failed vim-plug download removes temporary files"
  elif ! compgen -G "$TEST_HOME/.setup-backups/*/plug.vim" >/dev/null; then
    fail "preserves incomplete vim-plug before reacquiring it"
  else
    output="$(run_setup 2>&1)"
    status=$?
    if ((status != 0)); then
      fail "ordinary Setup rerun reacquires vim-plug ($output)"
    elif grep -Fq "plug#begin" "$TEST_HOME/.vim/autoload/plug.vim"; then
      pass "failed vim-plug download is atomic and safely rerunnable"
    fi
  fi

  cleanup_fixture
}

test_reports_all_missing_prerequisites
test_ordinary_setup_run_acquires_only_missing_dependencies
test_update_run_refreshes_clean_dependencies
test_update_run_rejects_modified_dependencies
test_update_run_rejects_diverged_dependencies
test_unchanged_configurations_are_untouched
test_failed_copy_preserves_existing_configuration
test_runtime_startup_has_no_dependency_side_effects
test_installed_vim_configuration_parses
test_installed_shell_configurations_parse
test_access_key_is_added_once_without_removing_existing_keys
test_ordinary_setup_run_recovers_incomplete_dependencies
test_ordinary_setup_run_recovers_incomplete_vim_plugins
test_failed_vim_plug_download_leaves_no_partial_installation

if ((failures > 0)); then
  printf '%d test(s) failed\n' "$failures" >&2
  exit 1
fi
