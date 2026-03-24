# Public aliases (diencephalon)

def cdd [] {
    let dir = (^cril wdir | str trim)
    if $dir != '' { cd $dir }
}
