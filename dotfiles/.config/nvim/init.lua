vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

-- Spell
vim.opt.spelllang = { "en", "en_gb" } -- or en_us
vim.opt.spellsuggest = "best,9"

local lazypath = vim.fn.stdpath 'data' .. '/lazy/lazy.nvim'
if not vim.loop.fs_stat(lazypath) then
  vim.fn.system {
    'git',
    'clone',
    '--filter=blob:none',
    'https://github.com/folke/lazy.nvim.git',
    '--branch=stable',
    lazypath,
  }
end
vim.opt.rtp:prepend(lazypath)

require('lazy').setup({
  'tpope/vim-fugitive',
  'tpope/vim-rhubarb',
  'tpope/vim-sleuth',
  {
    'neovim/nvim-lspconfig',
    dependencies = {
      'williamboman/mason.nvim',
      'williamboman/mason-lspconfig.nvim',
      { 'j-hui/fidget.nvim', opts = {} },
      'folke/lazydev.nvim',
    },
  },
  {
    'hrsh7th/nvim-cmp',
    dependencies = {
      'L3MON4D3/LuaSnip',
      'saadparwaiz1/cmp_luasnip',
      'hrsh7th/cmp-nvim-lsp',
      'rafamadriz/friendly-snippets',
    },
  },
  { 'folke/which-key.nvim',  opts = {} },
  {
    'lewis6991/gitsigns.nvim',
    opts = {
      signs = {
        add = { text = '+' },
        change = { text = '~' },
        delete = { text = '_' },
        topdelete = { text = '‾' },
        changedelete = { text = '~' },
      },
      on_attach = function(bufnr)
        local gs = package.loaded.gitsigns

        local function map(mode, l, r, opts)
          opts = opts or {}
          opts.buffer = bufnr
          vim.keymap.set(mode, l, r, opts)
        end

        -- Navigation
        map({ 'n', 'v' }, ']c', function()
          if vim.wo.diff then
            return ']c'
          end
          vim.schedule(function()
            gs.next_hunk()
          end)
          return '<Ignore>'
        end, { expr = true, desc = 'Jump to next hunk' })

        map({ 'n', 'v' }, '[c', function()
          if vim.wo.diff then
            return '[c'
          end
          vim.schedule(function()
            gs.prev_hunk()
          end)
          return '<Ignore>'
        end, { expr = true, desc = 'Jump to previous hunk' })

        -- Actions
        -- visual mode
        map('v', '<leader>hs', function()
          gs.stage_hunk { vim.fn.line '.', vim.fn.line 'v' }
        end, { desc = 'stage git hunk' })
        map('v', '<leader>hr', function()
          gs.reset_hunk { vim.fn.line '.', vim.fn.line 'v' }
        end, { desc = 'reset git hunk' })
        -- normal mode
        map('n', '<leader>hs', gs.stage_hunk, { desc = 'git stage hunk' })
        map('n', '<leader>hr', gs.reset_hunk, { desc = 'git reset hunk' })
        map('n', '<leader>hS', gs.stage_buffer, { desc = 'git Stage buffer' })
        map('n', '<leader>hu', gs.undo_stage_hunk, { desc = 'undo stage hunk' })
        map('n', '<leader>hR', gs.reset_buffer, { desc = 'git Reset buffer' })
        map('n', '<leader>hp', gs.preview_hunk, { desc = 'preview git hunk' })
        map('n', '<leader>hb', function()
          gs.blame_line { full = false }
        end, { desc = 'git blame line' })
        map('n', '<leader>hd', gs.diffthis, { desc = 'git diff against index' })
        map('n', '<leader>hD', function()
          gs.diffthis '~'
        end, { desc = 'git diff against last commit' })

        -- Toggles
        map('n', '<leader>tb', gs.toggle_current_line_blame, { desc = 'toggle git blame line' })
        map('n', '<leader>td', gs.toggle_deleted, { desc = 'toggle git show deleted' })

        -- Text object
        map({ 'o', 'x' }, 'ih', ':<C-U>Gitsigns select_hunk<CR>', { desc = 'select git hunk' })
      end,
    },
  },
  {
    'nvim-lualine/lualine.nvim',
    opts = {
      options = {
        icons_enabled = false,
        theme = 'onedark',
        component_separators = '|',
        section_separators = '',
      },
    },
  },
  {
    'lukas-reineke/indent-blankline.nvim',
    main = 'ibl',
    opts = {},
  },
  { 'numToStr/Comment.nvim', opts = {} },

  {
    'nvim-telescope/telescope.nvim',
    dependencies = {
      'nvim-lua/plenary.nvim',
      {
        'nvim-telescope/telescope-fzf-native.nvim',
        build = 'make',
        cond = function()
          return vim.fn.executable 'make' == 1
        end,
      },
    },
  },
  {
    'nvim-treesitter/nvim-treesitter',
    lazy = false,
    build = ':TSUpdate',
  },
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000
  },
  "ray-x/lsp_signature.nvim",
  { 'kevinhwang91/nvim-ufo', dependencies = { 'kevinhwang91/promise-async', } },
  "stevearc/conform.nvim",
  {
    "lervag/vimtex",
    ft = { "tex", "plaintex" },
  },
  {
    "benlubas/molten-nvim",
    version = "^1.0.0", -- use version <2.0.0 to avoid breaking changes
    build = ":UpdateRemotePlugins",
    init = function()
      -- these are examples, not defaults. Please see the readme
      vim.g.molten_image_provider = nil
      vim.g.molten_output_win_max_height = 20
      vim.g.molten_auto_open_output = true
    end,
  },

}, {})

vim.o.hlsearch = false

vim.wo.number = true
vim.wo.rnu = true

vim.o.clipboard = 'unnamedplus'
vim.o.breakindent = true
vim.o.undofile = true

vim.o.ignorecase = true
vim.o.smartcase = true

vim.wo.signcolumn = 'yes'

vim.o.updatetime = 250
vim.o.timeoutlen = 300

vim.o.completeopt = 'menuone,noselect'

vim.o.termguicolors = true

vim.o.foldcolumn = '1' -- '0' is not bad
vim.o.foldlevel = 99   -- Using ufo provider need a large value, feel free to decrease the value
vim.o.foldlevelstart = 99
vim.o.foldenable = true


-- personal keymaps
vim.keymap.set('n', '<leader>pv', vim.cmd.Ex, { desc = 'To file tree' })
vim.keymap.set('n', 'zR', require('ufo').openAllFolds)
vim.keymap.set('n', 'zM', require('ufo').closeAllFolds)

vim.keymap.set('n', '<leader>v', '"ayiw/<C-r>a<enter>', { desc = 'Search for word' })
vim.keymap.set('n', '<leader>y', '"ayy:!echo "<C-r>a"<enter>', { desc = 'Use line in command' })

vim.keymap.set('v', '<leader>p', '"_dP', { desc = "Paste without replacing buffer" })

--molten keymaps and config

vim.g.molten_cell_separator = "# %%"

local function get_cell_range()
  local sep = vim.g.molten_cell_separator
  local last_line = vim.fn.line("$")
  local curr_line = vim.fn.line(".")

  local start_line = 1
  for i = curr_line, 1, -1 do
    if vim.fn.getline(i):match("^%s*" .. vim.pesc(sep)) then
      start_line = i
      break
    end
  end

  local end_line = last_line
  for i = curr_line + 1, last_line do
    if vim.fn.getline(i):match("^%s*" .. vim.pesc(sep)) then
      end_line = i - 1
      break
    end
  end

  return start_line, end_line
end


function select_cell()
  local start, stop = get_cell_range()
  if start > stop then return end

  -- This works for both 'v' and 'o' modes
  vim.api.nvim_win_set_cursor(0, { start, 0 })
  vim.cmd("normal! V")
  vim.api.nvim_win_set_cursor(0, { stop, 0 })
end

function _G.molten_evaluate_cell()
  local start, stop = get_cell_range()
  if start > stop then return end

  local view = vim.fn.winsaveview()

  -- Directly select the range and trigger Molten
  vim.api.nvim_win_set_cursor(0, { start, 0 })
  vim.cmd("normal! V")
  vim.api.nvim_win_set_cursor(0, { stop, 0 })

  -- Execute the evaluation
  vim.cmd("MoltenEvaluateVisual")

  -- Reset to normal mode and restore cursor/view
  vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes("<Esc>", true, false, true), "nx", false)
  vim.fn.winrestview(view)
end

vim.keymap.set("x", "<leader>mc", ":<C-u>lua select_cell()<CR>", { silent = true, desc = "molten cell" })
vim.keymap.set("o", "<leader>mc", select_cell, { silent = true, desc = "molten cell" })
vim.keymap.set("n", "<leader>mm", molten_evaluate_cell, { desc = "Evaluate current cell" })


vim.keymap.set("n", "<localleader>mo", ":MoltenEvaluateOperator<CR>",
  { silent = true, desc = "run operator selection" })


local function molten_insert_cell_separator()
  vim.fn.append(vim.fn.line("."), vim.g.molten_cell_separator)
end

vim.keymap.set("n", "<localleader>mi", ":MoltenInit<CR>",
  { silent = true, desc = "Initialize the plugin" })
vim.keymap.set("n", "<localleader>mf", ":MoltenInfo<CR>",
  { silent = true, desc = "Initialize the plugin" })
vim.keymap.set("n", "<localleader>ml", ":MoltenEvaluateLine<CR>",
  { silent = true, desc = "evaluate line" })
vim.keymap.set("n", "<localleader>mr", ":MoltenReevaluateCell<CR>",
  { silent = true, desc = "re-evaluate cell" })
vim.keymap.set("v", "<localleader>mv", ":<C-u>MoltenEvaluateVisual<CR>gv",
  { silent = true, desc = "evaluate visual selection" })
vim.keymap.set("n", "<localleader>md", ":MoltenDelete<CR>",
  { silent = true, desc = "molten delete cell" })
vim.keymap.set("n", "<localleader>mh", ":MoltenHideOutput<CR>",
  { silent = true, desc = "hide output" })
vim.keymap.set("n", "<localleader>ms", ":noautocmd MoltenEnterOutput<CR>",
  { silent = true, desc = "show/enter output" })

vim.keymap.set("n", "<leader>m-", molten_insert_cell_separator,
  { desc = "Insert Molten cell separator" })

-- personal autocmds
--
vim.api.nvim_create_autocmd("FileType", {
  pattern = "nu",
  callback = function(event) vim.bo[event.buf].commentstring = "#! /usr/bin/env %s" end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "markdown", "tex", "plaintex", "xml" },
  callback = function()
    vim.opt_local.spell = true
    vim.opt_local.wrap = true
    vim.opt_local.linebreak = true
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = "markdown",
  callback = function()
    vim.opt_local.conceallevel = 2
    vim.opt_local.concealcursor = "nc"
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  callback = function(args)
    local lang = vim.treesitter.language.get_lang(args.match)
    if not lang then return end
    local max = 500 * 1024 -- 500 KB
    local ok, stats = pcall(vim.loop.fs_stat, vim.api.nvim_buf_get_name(args.buf))
    if ok and stats and stats.size > max then return end
    pcall(vim.treesitter.start, args.buf, lang)
  end,
})

-- Keymaps for better default experience
-- See `:help vim.keymap.set()`
vim.keymap.set({ 'n', 'v' }, '<Space>', '<Nop>', { silent = true })

-- Remap for dealing with word wrap
vim.keymap.set('n', 'k', "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })
vim.keymap.set('n', 'j', "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })

-- Diagnostic keymaps
vim.keymap.set('n', '[d', vim.diagnostic.goto_prev, { desc = 'Go to previous diagnostic message' })
vim.keymap.set('n', ']d', vim.diagnostic.goto_next, { desc = 'Go to next diagnostic message' })
vim.keymap.set('n', '<leader>e', vim.diagnostic.open_float, { desc = 'Open floating diagnostic message' })
vim.keymap.set('n', '<leader>q', vim.diagnostic.setloclist, { desc = 'Open diagnostics list' })

-- [[ Highlight on yank ]]
-- See `:help vim.highlight.on_yank()`
local highlight_group = vim.api.nvim_create_augroup('YankHighlight', { clear = true })
vim.api.nvim_create_autocmd('TextYankPost', {
  callback = function()
    vim.highlight.on_yank()
  end,
  group = highlight_group,
  pattern = '*',
})

-- [[ Configure Telescope ]]
-- See `:help telescope` and `:help telescope.setup()`

local ignore_pats = {
  '.git',
  '.dvc',
  '.venv',
  '.svelte-kit',
  'actions-runner',
  'node_modules',
  'build/',
  '__pycache__',
  'target',
  '.pytest_cache',
  '.coverage',
  'coverage.xml',
  'htmlcov/',
  -- '*.svg',
  '*.png',
  '*.jpg',
  '*.webp',
  '*.ipynb',
  '*.csv',
  '*.parquet',
  '*.xlsx',
  '*.lock',
  '*.gz',
  '*.zip',
  '*.whl',
}

require('telescope').setup {
  defaults = {
    mappings = {
      i = {
        ['<C-u>'] = false,
        ['<C-d>'] = false,
      },
    },
    -- no_ignore = true,
    file_ignore_patterns = ignore_pats,
  },
}

-- Enable telescope fzf native, if installed
pcall(require('telescope').load_extension, 'fzf')

-- Telescope live_grep in git root
local function find_git_root()
  -- Use the current buffer's path as the starting point for the git search
  local current_file = vim.api.nvim_buf_get_name(0)
  local current_dir
  local cwd = vim.fn.getcwd()
  -- If the buffer is not associated with a file, return nil
  if current_file == '' then
    current_dir = cwd
  else
    -- Extract the directory from the current file's path
    current_dir = vim.fn.fnamemodify(current_file, ':h')
  end

  -- Find the Git root directory from the current file's path
  local git_root = vim.fn.systemlist('git -C ' .. vim.fn.escape(current_dir, ' ') .. ' rev-parse --show-toplevel')[1]
  if vim.v.shell_error ~= 0 then
    print 'Not a git repository. Searching on current working directory'
    return cwd
  end
  return git_root
end

-- Custom live_grep function to search in git root

local tele_std = require('telescope.builtin')

local function live_grep_git_root()
  local git_root = find_git_root()
  if git_root then
    tele_std.live_grep {
      search_dirs = { git_root },
    }
  end
end

vim.api.nvim_create_user_command('LiveGrepGitRoot', live_grep_git_root, {})

local function find_files_spec()
  local command = { 'rg',
    '--files',
    '--hidden',
  }
  for _, v in pairs(ignore_pats) do
    table.insert(command, "--iglob")
    table.insert(command, "!" .. v)
  end
  tele_std.find_files {
    find_command = command,
    previewer = true,
    no_ignore = true,
  }
end

-- See `:help telescope.builtin`
vim.keymap.set('n', '<leader>?', tele_std.oldfiles, { desc = '[?] Find recently opened files' })
vim.keymap.set('n', '<leader><space>', tele_std.buffers, { desc = '[ ] Find existing buffers' })
vim.keymap.set('n', '<leader>/', function()
  -- You can pass additional configuration to telescope to change theme, layout, etc.
  tele_std.current_buffer_fuzzy_find(require('telescope.themes').get_dropdown {
    winblend = 10,
    previewer = false,
  })
end, { desc = '[/] Fuzzily search in current buffer' })

local function telescope_live_grep_open_files()
  tele_std.live_grep {
    grep_open_files = true,
    prompt_title = 'Live Grep in Open Files',
  }
end


local function telescope_live_grep_clean()
  local iglobs = {}
  for _, v in pairs(ignore_pats) do
    table.insert(iglobs, "!" .. v)
  end
  tele_std.live_grep {
    glob_pattern = iglobs
  }
end


local function telescope_todo()
  tele_std.grep_string { search = 'TODO' }
end


vim.keymap.set('n', '<leader>s/', telescope_live_grep_open_files, { desc = '[S]earch [/] in Open Files' })
vim.keymap.set('n', '<leader>ss', tele_std.builtin, { desc = '[S]earch [S]elect Telescope' })
vim.keymap.set('n', '<leader>gf', tele_std.git_files, { desc = 'Search [G]it [F]iles' })
vim.keymap.set('n', '<leader>sf', find_files_spec, { desc = '[S]earch [F]iles' })
vim.keymap.set('n', '<leader>st', telescope_todo, { desc = '[S]earch [T]odo' })
vim.keymap.set('n', '<leader>sh', tele_std.help_tags, { desc = '[S]earch [H]elp' })
vim.keymap.set('n', '<leader>sw', tele_std.grep_string, { desc = '[S]earch current [W]ord' })
vim.keymap.set('n', '<leader>sg', telescope_live_grep_clean, { desc = '[S]earch by [G]rep' })
vim.keymap.set('n', '<leader>sG', ':LiveGrepGitRoot<cr>', { desc = '[S]earch by [G]rep on Git Root' })
vim.keymap.set('n', '<leader>sd', tele_std.diagnostics, { desc = '[S]earch [D]iagnostics' })
vim.keymap.set('n', '<leader>sr', tele_std.resume, { desc = '[S]earch [R]esume' })

-- Git keymaps
vim.keymap.set('n', '<leader>gs', ":Git status<enter>", { desc = '[G]it [S]tatus' })
vim.keymap.set('n', '<leader>gd', ":Gdiffsplit<enter>", { desc = '[G]it [D]iff' })
vim.keymap.set('n', '<leader>ga', ":Git add %<enter>", { desc = '[G]it [A]dd' })
vim.keymap.set('n', '<leader>gc', ":Git commit -m \"\"<Left>", { desc = '[G]it [C]ommit' })
vim.keymap.set('n', '<leader>gp', ":Git push<enter>", { desc = '[G]it [P]ush' })
vim.keymap.set('n', '<leader>gl', ":Git pull<enter>", { desc = '[G]it Pul[l]' })
vim.keymap.set('n', '<leader>gw', ":Git add % | Git commit -m \"\"<Left>", { desc = '[G]it [W]rite' })
vim.keymap.set("n", "<leader>gh", function()
  local file = vim.fn.expand("%")
  local line = vim.fn.line(".")
  local start_line = line - 5
  local end_line = line + 5
  if 0 > start_line then
    start_line = 0
  end
  local cmd = string.format("Git log -L %d,%d:%s", start_line, end_line, file)
  vim.cmd(cmd)
end, { desc = "[G]it commit [H]istory (log) for current line" })

-- Spellcheck keymaps
--
vim.keymap.set("n", "]s", "]s", { desc = "Next misspelled word" })
vim.keymap.set("n", "[s", "[s", { desc = "Prev misspelled word" })
vim.keymap.set("n", "zg", "zg", { desc = "Add word to dictionary" })
vim.keymap.set("n", "zw", "zw", { desc = "Mark word as wrong" })
vim.keymap.set("n", "z=", "z=", { desc = "Spelling suggestions" })

-- [[ Configure Treesitter ]]
-- See `:help nvim-treesitter`
-- Defer Treesitter setup after first render to improve startup time of 'nvim {filename}'

require('nvim-treesitter').install({
  'markdown',
  'markdown_inline',
  'latex',
  'bibtex',
  'xml',
  'c',
  'cpp',
  'go',
  'lua',
  'python',
  'rust',
  'tsx',
  'javascript',
  'typescript',
  'vimdoc',
  'vim',
  'bash',
  'html',
  'svelte',
  'nu'

})


require('which-key').add {
  { '<leader>c', group = '[C]ode' },
  { '<leader>d', group = '[D]ocument' },
  { '<leader>g', group = '[G]it' },
  { '<leader>r', group = '[R]ename' },
  { '<leader>s', group = '[S]earch' },
  { '<leader>w', group = '[W]orkspace' },
  { '<leader>t', group = '[T]oggle' },
  { '<leader>m', group = '[M]olten' },
  { '<leader>h', group = 'Git [H]unk',      mode = { 'n', 'v' } },
  { "<leader>",  group = "VISUAL <leader>", mode = "v" },
}
require('catppuccin').setup({ flavour = "mocha", transparent_background = true })
vim.cmd.colorscheme "catppuccin"

-- require("eslint").setup({
--   bin = 'eslint', -- or `eslint_d`
--   code_actions = {
--     enable = false,
--     apply_on_save = {
--       enable = false,
--       types = { "directive", "problem", "suggestion", "layout" },
--     },
--   },
--   diagnostics = {
--     enable = true,
--     report_unused_disable_directives = false,
--     run_on = "type", -- or `save`
--   },
-- })



-- [[ Configure LSP ]]
-- Add this near the top of your config
local on_attach = function(client, bufnr)
  local nmap = function(keys, func, desc)
    if desc then
      desc = 'LSP: ' .. desc
    end
    vim.keymap.set('n', keys, func, { buffer = bufnr, desc = desc })
  end

  nmap('<leader>rn', vim.lsp.buf.rename, '[R]e[n]ame')
  nmap('<leader>ca', vim.lsp.buf.code_action, '[C]ode [A]ction')
  nmap('gd', tele_std.lsp_definitions, '[G]oto [D]efinition')
  nmap('gr', tele_std.lsp_references, '[G]oto [R]eferences')
  nmap('gI', tele_std.lsp_implementations, '[G]oto [I]mplementation')
  nmap('<leader>D', tele_std.lsp_type_definitions, 'Type [D]efinition')
  nmap('<leader>ds', tele_std.lsp_document_symbols, '[D]ocument [S]ymbols')
  nmap('<leader>ws', tele_std.lsp_dynamic_workspace_symbols, '[W]orkspace [S]ymbols')
  -- See `:help K` for why this keymap
  nmap('K', vim.lsp.buf.hover, 'Hover Documentation')
  nmap('<C-k>', vim.lsp.buf.signature_help, 'Signature Documentation')
  -- Lesser used LSP functionality
  nmap('gD', vim.lsp.buf.declaration, '[G]oto [D]eclaration')
  nmap('<leader>wa', vim.lsp.buf.add_workspace_folder, '[W]orkspace [A]dd Folder')
  nmap('<leader>wr', vim.lsp.buf.remove_workspace_folder, '[W]orkspace [R]emove Folder')
  nmap('<leader>wl', function()
    print(vim.inspect(vim.lsp.buf.list_workspace_folders()))
  end, '[W]orkspace [L]ist Folders')
end
vim.lsp.set_log_level("WARN")
-- And add this autocmd to see when LSP clients start
vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    local bufnr = args.buf
    -- print("LspAttach triggered for client:", client.name, "on buffer:", args.buf)
    on_attach(client, bufnr)
  end,
})

require('Comment').setup()
require('lsp_signature').setup()
-- mason-lspconfig requires that these setup functions are called in this order
-- before setting up the servers.
require('mason').setup()
require('lazydev').setup()
local servers = {
  -- clangd = {},
  -- gopls = {},
  texlab = {
    texlab = {
      build = {
        executable = "latexmk",
        args = { "-pdf", "-interaction=nonstopmode", "-synctex=1", "%f" },
        onSave = true,
      },
      forwardSearch = {
        executable = "zathura",
        args = { "--synctex-forward", "%l:1:%f", "%p" },
      },
    },
  },
  lemminx = {
    xml = {
      server = {
        workDir = "~/.cache/lemminx", -- location for cache
      }
    }
  },
  pyright = {},
  rust_analyzer = {},
  ts_ls = {},
  html = { filetypes = { 'html', 'twig', 'hbs' } },
  svelte = { filetypes = { 'svelte' } },
  lua_ls = {
    Lua = {
      workspace = { checkThirdParty = false },
      telemetry = { enable = false },
      -- NOTE: toggle below to ignore Lua_LS's noisy `missing-fields` warnings
      diagnostics = { disable = { 'missing-fields' }, globals = { 'vim' } },
    },
  },
}
-- nvim-cmp supports additional completion capabilities, so broadcast that to servers
local capabilities = vim.lsp.protocol.make_client_capabilities()
capabilities = require('cmp_nvim_lsp').default_capabilities(capabilities)
require('mason-lspconfig').setup {
  ensure_installed = vim.tbl_keys(servers),
  handlers = {
    function(server_name)
      local server_config = {
        capabilities = capabilities,
        settings = servers[server_name],
        filetypes = (servers[server_name] or {}).filetypes,
      }
      if server_name == "rust_analyzer" then
        local ra_path = vim.fn.trim(vim.fn.system("rustup which rust-analyzer"))
        server_config.cmd = { ra_path }
      end
      require('lspconfig')[server_name].setup(server_config)
    end,
  }
}

require('ufo').setup({
  provider_selector = function(bufnr, filetype, buftype)
    return { 'treesitter', 'indent' }
  end
})

require("conform").setup({
  formatters_by_ft = {
    lua = { "stylua" },
    python = { "isort", "black" },
    javascript = { "prettierd", "prettier" },
    css = { "prettierd", "prettier" },
  },
  format_on_save = function(bufnr)
    local ft = vim.bo[bufnr].filetype
    return {
      timeout_ms = 500,
      lsp_fallback = true,
      stop_after_first = (ft == "css" or ft == "javascript"),
    }
  end,
})

-- [[ Configure nvim-cmp ]]
-- See `:help cmp`
local cmp = require 'cmp'
local luasnip = require 'luasnip'
require('luasnip.loaders.from_vscode').lazy_load()
luasnip.config.setup {}

cmp.setup {
  snippet = {
    expand = function(args)
      luasnip.lsp_expand(args.body)
    end,
  },
  completion = {
    completeopt = 'menu,menuone,noinsert',
  },
  mapping = cmp.mapping.preset.insert {
    ['<C-n>'] = cmp.mapping.select_next_item(),
    ['<C-p>'] = cmp.mapping.select_prev_item(),
    ['<C-d>'] = cmp.mapping.scroll_docs(-4),
    ['<C-f>'] = cmp.mapping.scroll_docs(4),
    ['<C-Space>'] = cmp.mapping.complete {},
    ['<CR>'] = cmp.mapping.confirm {
      behavior = cmp.ConfirmBehavior.Replace,
      select = true,
    },
    ['<Tab>'] = cmp.mapping(function(fallback)
      if cmp.visible() then
        cmp.select_next_item()
      elseif luasnip.expand_or_locally_jumpable() then
        luasnip.expand_or_jump()
      else
        fallback()
      end
    end, { 'i', 's' }),
    ['<S-Tab>'] = cmp.mapping(function(fallback)
      if cmp.visible() then
        cmp.select_prev_item()
      elseif luasnip.locally_jumpable(-1) then
        luasnip.jump(-1)
      else
        fallback()
      end
    end, { 'i', 's' }),
  },
  sources = {
    { name = 'nvim_lsp' },
    { name = 'luasnip' },
  },
}


vim.g.vimtex_view_method = "zathura" -- or "skim", "okular", "sioyek"
vim.g.vimtex_compiler_method = "latexmk"
vim.g.vimtex_quickfix_mode = 0
vim.g.vimtex_syntax_enabled = 1
vim.g.vimtex_fold_enabled = 1

-- The line beneath this is called `modeline`. See `:help modeline`
-- vim: ts=2 sts=2 sw=2 et
