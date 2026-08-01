# Public aliases (diencephalon)

[ -f ~/.local-aliases ] && . ~/.local-aliases

# Claude model aliases — bump a tier here when a new version ships
CLAUDE_OPUS=claude-opus-5
CLAUDE_SONNET=claude-sonnet-5
CLAUDE_HAIKU=claude-haiku-4-5
CLAUDE_FABLE=claude-fable-5

alias clhai="claude --model $CLAUDE_HAIKU"
alias clopuh="claude --model $CLAUDE_OPUS --effort high"
alias clopux="claude --model $CLAUDE_OPUS --effort xhigh"
alias clopuxa="claude --model $CLAUDE_OPUS --effort xhigh --permission-mode auto"
alias clopum="claude --model $CLAUDE_OPUS --effort max"
alias clsoh="claude --model $CLAUDE_SONNET --effort high"
alias clsom="claude --model $CLAUDE_SONNET --effort medium"
alias clfab="claude --model $CLAUDE_FABLE --effort xhigh"
unset CLAUDE_OPUS CLAUDE_SONNET CLAUDE_HAIKU CLAUDE_FABLE

alias gwc="watch -n 1 -c git -c color.status=always status"
alias datefmt="date +%Y-%m-%d-%H-%M-%S"
alias dcuw="dienpy claude usage --w"
alias daic="dienpy ai commit"
alias speak="dienpy tts speak"
