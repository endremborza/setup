#! /usr/bin/env nu
let CWS = (leftwm-state --quit | jq '.workspaces[]  | select(any(.tags[]; .mine and .focused)).index')
let BG_NAME = "main-bg"

let tfound = (tmux has-session -t $BG_NAME | complete | get exit_code)
if ($tfound == 1) {
	tmux new-session -ds $BG_NAME
}
[ "xdotool key Super_L+f", "alacritty -e nu", "alacritty -e nu", Logseq, nautilus, "alacritty -e btop" ] | enumerate | each {
	|e| leftwm-command $"SendWorkspaceToTag ($CWS) ($e.index)"; tmux new-window -t $BG_NAME $e.item; sleep 0.3sec
}
tmux attach-session -t $BG_NAME


