# Public aliases (diencephalon)

[ -f ~/.local-aliases ] && . ~/.local-aliases
alias clhai="claude --model claude-haiku-4-5"
alias clopuh="claude --model claude-opus-4-8 --effort high"
alias clopux="claude --model claude-opus-4-8 --effort xhigh"
alias clopuxa="claude --model claude-opus-4-8 --effort xhigh --permission-mode auto"
alias clopum="claude --model claude-opus-4-8 --effort max"
alias clsoh="claude --model claude-sonnet-5 --effort high"
alias clsom="claude --model claude-sonnet-5 --effort medium"
alias clfab="claude --model claude-fable-5 --effort xhigh"
alias gwc="watch -n 1 -c git -c color.status=always status"
alias datefmt="date +%Y-%m-%d-%H-%M-%S"
alias dcuw="dienpy claude usage --w"
alias daic="dienpy ai commit"
alias speak="dienpy tts speak"
