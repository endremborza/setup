# Public aliases (diencephalon)

[ -f ~/.local-aliases ] && . ~/.local-aliases

# Claude sessions — profiles (model, effort) live in moac._profiles.BUILTIN
alias clhai="moac run --interactive haiku"
alias clsoh="moac run --interactive soh"
alias clsom="moac run --interactive som"
alias clopuh="moac run --interactive opuh"
alias clopux="moac run --interactive opux"
alias clopuxa="moac run --interactive --auto opux"
alias clopum="moac run --interactive opum"
alias clfab="moac run --interactive fabx"
alias pipecl="moac run opux"
alias pipeclf="moac run fabx"

alias gwc="watch -n 1 -c git -c color.status=always status"
alias datefmt="date +%Y-%m-%d-%H-%M-%S"
alias dcuw="moac usage --w"
alias hunks="dienpy hunks run opus normal explore"
alias hunksmin="dienpy hunks run sonnet normal agents"
alias dhs="dienpy hunks run --staged"
alias speak="dienpy tts speak"

# Aliases onto protocli tools complete like the tool. Until a tool's script loads,
# this stub loads it on the alias's first TAB; the script replaces the stub.
_proto_dir=~/.local/share/bash-completion/completions
_proto_alias_complete() {
    . "$_proto_dir/${BASH_ALIASES[$1]%% *}" && declare -F _proto_reply >/dev/null && _proto_alias_complete "$@"
}
for _a in "${!BASH_ALIASES[@]}"; do
    _t=$_proto_dir/${BASH_ALIASES[$_a]%% *}
    [[ -f $_t ]] && read -r _l <"$_t" && [[ $_l == *--bash-completion* ]] && complete -F _proto_alias_complete "$_a"
done
unset _a _t _l
