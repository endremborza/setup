# Public aliases (diencephalon)

[ -f ~/.local-aliases ] && . ~/.local-aliases

# Claude sessions — profiles (model, effort) live in dienpy.ai._profiles.BUILTIN
alias clhai="dienpy ai run --interactive haiku"
alias clsoh="dienpy ai run --interactive soh"
alias clsom="dienpy ai run --interactive som"
alias clopuh="dienpy ai run --interactive opuh"
alias clopux="dienpy ai run --interactive opux"
alias clopuxa="dienpy ai run --interactive --auto opux"
alias clopum="dienpy ai run --interactive opum"
alias clfab="dienpy ai run --interactive fabx"
alias pipecl="dienpy ai run opux"
alias pipeclf="dienpy ai run fabx"

alias gwc="watch -n 1 -c git -c color.status=always status"
alias datefmt="date +%Y-%m-%d-%H-%M-%S"
alias dcuw="dienpy claude usage --w"
alias hunks="dienpy hunks run opus normal explore"
alias hunksmin="dienpy hunks run sonnet normal agents"
alias dhs="dienpy hunks run --staged"
alias speak="dienpy tts speak"

_proto=~/.local/share/bash-completion/completions/_proto_complete
[ -f "$_proto" ] && . "$_proto" && _proto_register_aliases
unset _proto
