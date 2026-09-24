vim.g.mapleader = ' '
vim.g.maplocalleader = ' '

vim.opt.spelllang = { "en", "en_gb" }
vim.opt.spellsuggest = "best,9"

local lazypath = vim.fn.stdpath 'data' .. '/lazy/lazy.nvim'
if not vim.uv.fs_stat(lazypath) then
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

-- lspconfig's rust root_dir shells out to rustc and cargo on every open; the lockfile marks
-- the workspace root without either. Files under the toolchain or the registry join the
-- running server, so goto-definition into std never starts a second one.
local function rust_root(fname)
  local home = vim.fs.normalize(vim.env.HOME)
  for _, dir in ipairs({ vim.env.CARGO_HOME or home .. '/.cargo', vim.env.RUSTUP_HOME or home .. '/.rustup' }) do
    if vim.fs.relpath(dir, fname) then
      local clients = vim.lsp.get_clients { name = 'rust_analyzer' }
      if #clients > 0 then return clients[#clients].config.root_dir end
    end
  end
  return vim.fs.root(fname, { 'Cargo.lock', 'rust-project.json' })
      or vim.fs.root(fname, { 'Cargo.toml' })
      or vim.fs.root(fname, { '.git' })
end

-- one table drives the plugin's cmd trigger and its keymaps
local MOLTEN = {
  { 'i', 'MoltenInit', 'initialize the plugin' },
  { 'f', 'MoltenInfo', 'plugin info' },
  { 'l', 'MoltenEvaluateLine', 'evaluate line' },
  { 'r', 'MoltenReevaluateCell', 're-evaluate cell' },
  { '0', 'MoltenRestart', 'restart kernel' },
  { 'v', 'MoltenEvaluateVisual', 'run selection', mode = 'v' },
  { 'd', 'MoltenDelete', 'delete cell' },
  { 'h', 'MoltenHideOutput', 'hide output' },
  { 'o', 'MoltenShowOutput', 'show output' },
  { 's', 'MoltenEnterOutput', 'show/enter output', prefix = 'noautocmd ' },
  { 'n', 'MoltenNext', 'next cell' },
  { 'b', 'MoltenPrev', 'previous cell' },
}

local function molten_spec()
  local cmd, keys = {}, {}
  for _, m in ipairs(MOLTEN) do
    table.insert(cmd, m[2])
    local rhs = m.mode == 'v' and (':<C-u>' .. m[2] .. '<CR>gv') or ('<cmd>' .. (m.prefix or '') .. m[2] .. '<CR>')
    table.insert(keys, { '<localleader>m' .. m[1], rhs, mode = m.mode or 'n', desc = m[3], silent = true })
  end
  return cmd, keys
end

local function tele(fn, opts)
  return function() require('telescope.builtin')[fn](opts) end
end

require('lazy').setup({
  { 'tpope/vim-fugitive', event = "VeryLazy" },
  { 'tpope/vim-rhubarb',  event = "VeryLazy" },
  { 'tpope/vim-sleuth',   event = "BufReadPre" },
  {
    'neovim/nvim-lspconfig',
    event = { "BufReadPre", "BufNewFile" },
    dependencies = {
      'williamboman/mason.nvim',
      'williamboman/mason-lspconfig.nvim',
      { 'j-hui/fidget.nvim', opts = {} },
      {
        'folke/lazydev.nvim',
        ft = 'lua',
        opts = {
          library = {
            { path = '${3rd}/luv/library', words = { 'vim%.uv' } },
          },
        },
      },
      'hrsh7th/cmp-nvim-lsp',
    },
    config = function()
      -- no server for fugitive://, gitsigns://, term:// and other non-file buffers
      local orig_lsp_start = vim.lsp.start
      vim.lsp.start = function(config, opts)
        opts = opts or {}
        local bufnr = opts.bufnr or vim.api.nvim_get_current_buf()
        if not vim.api.nvim_buf_get_name(bufnr):match("^/") then return nil end
        return orig_lsp_start(config, opts)
      end

      local capabilities = vim.lsp.protocol.make_client_capabilities()
      capabilities = require('cmp_nvim_lsp').default_capabilities(capabilities)
      capabilities = vim.tbl_deep_extend("force", capabilities, {
        workspace = { didChangeWatchedFiles = { dynamicRegistration = false } },
      })

      vim.lsp.config('*', { capabilities = capabilities })

      vim.lsp.config('pyright', {
        settings = {
          python = {
            analysis = {
              exclude = { ".venv", "**/.venv", "**/node_modules" },
            },
          },
        },
      })

      vim.lsp.config('rust_analyzer', {
        root_dir = function(bufnr, on_dir)
          local fname = vim.api.nvim_buf_get_name(bufnr)
          if not fname:match("^/") then return end
          local root = rust_root(fname)
          if root then on_dir(root) end
        end,
      })

      vim.lsp.config('html', { filetypes = { 'html', 'twig', 'hbs' } })

      vim.lsp.config('lua_ls', {
        settings = {
          Lua = {
            workspace = { checkThirdParty = false },
            telemetry = { enable = false },
            diagnostics = { disable = { 'missing-fields' }, globals = { 'vim' } },
          },
        },
      })

      require('mason').setup()
      require('mason-lspconfig').setup {
        ensure_installed = { 'texlab', 'lemminx', 'pyright', 'rust_analyzer', 'ts_ls', 'html', 'svelte', 'lua_ls' },
        automatic_enable = true,
      }
      vim.lsp.enable('ruff')
      vim.lsp.log.set_level(vim.log.levels.WARN)

      -- telescope-backed variants of the LSP defaults (grr stays the references key);
      -- rename, code action, hover and diagnostics use the defaults
      vim.api.nvim_create_autocmd("LspAttach", {
        callback = function(args)
          local tb = require('telescope.builtin')
          local function nmap(keys, func, desc)
            vim.keymap.set('n', keys, func, { buffer = args.buf, desc = 'LSP: ' .. desc })
          end
          nmap('gd', tb.lsp_definitions, '[G]oto [D]efinition')
          nmap('grr', tb.lsp_references, '[G]oto [R]eferences')
          nmap('gI', tb.lsp_implementations, '[G]oto [I]mplementation')
          nmap('<leader>D', tb.lsp_type_definitions, 'Type [D]efinition')
          nmap('<leader>ds', tb.lsp_document_symbols, '[D]ocument [S]ymbols')
          nmap('<leader>ws', tb.lsp_dynamic_workspace_symbols, '[W]orkspace [S]ymbols')
          nmap('<C-k>', vim.lsp.buf.signature_help, 'Signature Documentation')
          nmap('gD', vim.lsp.buf.declaration, '[G]oto [D]eclaration')
        end,
      })
    end,
  },
  {
    'hrsh7th/nvim-cmp',
    event = "InsertEnter",
    dependencies = {
      'hrsh7th/cmp-nvim-lsp',
      'hrsh7th/cmp-path',
    },
    config = function()
      local cmp = require 'cmp'
      cmp.setup {
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
            if cmp.visible() then cmp.select_next_item() else fallback() end
          end, { 'i', 's' }),
          ['<S-Tab>'] = cmp.mapping(function(fallback)
            if cmp.visible() then cmp.select_prev_item() else fallback() end
          end, { 'i', 's' }),
        },
        sources = {
          { name = 'nvim_lsp' },
          { name = 'path',    option = { get_cwd = function() return vim.fn.getcwd() end } },
        },
      }
    end,
  },
  {
    'folke/which-key.nvim',
    event = "VeryLazy",
    config = function()
      require('which-key').setup {}
      require('which-key').add {
        { "]s",        desc = "Next misspelled word" },
        { "[s",        desc = "Prev misspelled word" },
        { "zg",        desc = "Add word to dictionary" },
        { "zw",        desc = "Mark word as wrong" },
        { "z=",        desc = "Spelling suggestions" },
        { '<leader>d', group = '[D]ocument' },
        { '<leader>f', group = '[F]ile' },
        { '<leader>g', group = '[G]it' },
        { '<leader>i', group = '[I]nsert' },
        { '<leader>s', group = '[S]earch' },
        { '<leader>w', group = '[W]orkspace' },
        { '<leader>t', group = '[T]oggle' },
        { '<leader>m', group = '[M]olten' },
        { '<leader>h', group = 'Git [H]unk',           mode = { 'n', 'v' } },
        { "<leader>",  group = "VISUAL <leader>",      mode = "v" },
      }
    end,
  },
  {
    'lewis6991/gitsigns.nvim',
    event = { "BufReadPre", "BufNewFile" },
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

        map({ 'n', 'v' }, ']c', function()
          if vim.wo.diff then
            vim.cmd.normal({ ']c', bang = true })
          else
            gs.nav_hunk('next')
          end
        end, { desc = 'Jump to next hunk' })

        map({ 'n', 'v' }, '[c', function()
          if vim.wo.diff then
            vim.cmd.normal({ '[c', bang = true })
          else
            gs.nav_hunk('prev')
          end
        end, { desc = 'Jump to previous hunk' })

        map('v', '<leader>hs', function()
          gs.stage_hunk { vim.fn.line '.', vim.fn.line 'v' }
        end, { desc = 'stage git hunk' })
        map('v', '<leader>hr', function()
          gs.reset_hunk { vim.fn.line '.', vim.fn.line 'v' }
        end, { desc = 'reset git hunk' })
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

        map('n', '<leader>tb', gs.toggle_current_line_blame, { desc = 'toggle git blame line' })
        map('n', '<leader>td', gs.toggle_deleted, { desc = 'toggle git show deleted' })

        map({ 'o', 'x' }, 'ih', ':<C-U>Gitsigns select_hunk<CR>', { desc = 'select git hunk' })
      end,
    },
  },
  {
    'nvim-lualine/lualine.nvim',
    opts = {
      options = {
        icons_enabled = false,
        theme = 'catppuccin-mocha',
        component_separators = '|',
        section_separators = '',
      },
    },
  },
  {
    'lukas-reineke/indent-blankline.nvim',
    event = "BufReadPost",
    main = 'ibl',
    opts = {},
  },
  {
    'nvim-telescope/telescope.nvim',
    cmd = 'Telescope',
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
    keys = {
      { '<leader>gf', function() require('regroup.review').pick_file() end, desc = 'Review changed [F]ile' },
      { '<leader>gb', function() require('regroup.review').pick_base() end, desc = 'Review [B]asis branch' },
      { '<leader>go', tele('git_branches'), desc = 'Check[O]ut Branch' },
      { '<leader>fh', tele('git_bcommits'), desc = '[F]ile commit [H]istory' },
      { '<leader>?', tele('oldfiles'), desc = '[?] Find recently opened files' },
      { '<leader><space>', tele('buffers'), desc = '[ ] Find existing buffers' },
      {
        '<leader>/',
        function()
          require('telescope.builtin').current_buffer_fuzzy_find(
            require('telescope.themes').get_dropdown { winblend = 10, previewer = false })
        end,
        desc = '[/] Fuzzily search in current buffer',
      },
      { '<leader>s/', tele('live_grep', { grep_open_files = true, prompt_title = 'Live Grep in Open Files' }), desc = '[S]earch [/] in Open Files' },
      { '<leader>ss', tele('builtin'), desc = '[S]earch [S]elect Telescope' },
      { '<leader>sf', tele('find_files'), desc = '[S]earch [F]iles' },
      { '<leader>st', tele('grep_string', { search = 'TODO' }), desc = '[S]earch [T]odo' },
      { '<leader>sh', tele('help_tags'), desc = '[S]earch [H]elp' },
      { '<leader>sw', tele('grep_string'), desc = '[S]earch current [W]ord' },
      { '<leader>sg', tele('live_grep'), desc = '[S]earch by [G]rep' },
      { '<leader>sd', tele('diagnostics'), desc = '[S]earch [D]iagnostics' },
      { '<leader>sr', tele('resume'), desc = '[S]earch [R]esume' },
    },
    config = function()
      local ignore_file = vim.fn.expand("~/.config/ignore_patterns")

      local search_flags = {
        "--no-ignore-vcs",
        "--follow",
        "--ignore-file", ignore_file,
        '--hidden',
      }

      require('telescope').setup {
        defaults = {
          mappings = {
            i = {
              ['<C-u>'] = false,
              ['<C-d>'] = false,
            },
          },
          vimgrep_arguments = {
            "rg", "--color=never", "--no-heading", "--with-filename",
            "--line-number", "--column", "--smart-case",
            unpack(search_flags),
          },
        },
        pickers = {
          find_files = {
            find_command = { "fd", "--type", "f", unpack(search_flags) },
          },
        },
      }

      pcall(require('telescope').load_extension, 'fzf')
    end,
  },
  {
    'nvim-treesitter/nvim-treesitter',
    lazy = false,
    build = ':TSUpdate',
    config = function()
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
      })
    end,
  },
  {
    'MeanderingProgrammer/render-markdown.nvim',
    ft = 'markdown',
    cmd = 'RenderMarkdown',
    keys = { { '<leader>tm', '<cmd>RenderMarkdown toggle<CR>', desc = 'toggle markdown render' } },
    opts = {
      -- tables are stored compact (`| a | b |`); the padding that aligns them is virtual text
      heading = { enabled = false },
      code = { enabled = false },
      bullet = { enabled = false },
      checkbox = { enabled = false },
      quote = { enabled = false },
      link = { enabled = false },
      sign = { enabled = false },
      pipe_table = { preset = 'round', cell = 'padded' },
      -- the row under the cursor stays rendered, so moving down a table does not break it up
      anti_conceal = { enabled = false },
      win_options = { conceallevel = { rendered = 2 } },
    },
  },
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    config = function()
      require('catppuccin').setup({ flavour = "mocha", transparent_background = true })
      vim.cmd.colorscheme "catppuccin"
    end,
  },
  {
    'kevinhwang91/nvim-ufo',
    event = "BufReadPost",
    dependencies = { 'kevinhwang91/promise-async' },
    config = function()
      require('ufo').setup({
        provider_selector = function(bufnr, filetype, buftype)
          if buftype ~= '' then return '' end
          local name = vim.api.nvim_buf_get_name(bufnr)
          if not name:match("^/") then return '' end
          return { 'treesitter', 'indent' }
        end
      })
    end,
  },
  {
    "stevearc/conform.nvim",
    event = "BufWritePre",
    cmd = "ConformInfo",
    config = function()
      require("conform").setup({
        formatters_by_ft = {
          lua = { "stylua" },
          python = { "ruff_format" },
          javascript = { "prettierd", "prettier" },
          css = { "prettierd", "prettier" },
          xml = { "xmllint" },
        },
        -- a formatter that is not installed falls through to the attached LSP
        format_on_save = function(bufnr)
          local ft = vim.bo[bufnr].filetype
          return {
            timeout_ms = 500,
            lsp_format = "fallback",
            stop_after_first = (ft == "css" or ft == "javascript"),
          }
        end,
      })
    end,
  },
  {
    -- vimtex owns compiling and viewing; texlab stays an LSP only
    "lervag/vimtex",
    ft = { "tex", "plaintex" },
    config = function()
      vim.g.vimtex_view_method = "zathura"
      vim.g.vimtex_compiler_method = "tectonic"
      vim.g.vimtex_quickfix_mode = 0
      vim.g.vimtex_syntax_enabled = 1
      vim.g.vimtex_fold_enabled = 1
    end,
  },
  {
    'Julian/lean.nvim',
    event = { 'BufReadPre *.lean', 'BufNewFile *.lean' },

    dependencies = {
      'nvim-lua/plenary.nvim',
    },
    ---@type lean.Config
    opts = {
      mappings = true,
    }
  },
  (function()
    local cmd, keys = molten_spec()
    return {
      "benlubas/molten-nvim",
      version = "^1.0.0",
      build = ":UpdateRemotePlugins",
      cmd = cmd,
      keys = keys,
      init = function()
        vim.g.molten_output_win_max_height = 20
        vim.g.molten_auto_open_output = true
      end,
    }
  end)(),
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

vim.o.autoread = true
vim.o.updatetime = 250
vim.o.timeoutlen = 300

vim.o.termguicolors = true

vim.o.diffopt = table.concat({
  "internal",
  "filler",
  "closeoff",
  "algorithm:histogram",
  "linematch:20",
}, ",")

vim.o.foldcolumn = '1'
vim.o.foldlevel = 99
vim.o.foldlevelstart = 99
vim.o.foldenable = true

vim.keymap.set('n', '<leader>pv', vim.cmd.Ex, { desc = 'To file tree' })
vim.keymap.set('n', 'zR', function() require('ufo').openAllFolds() end)
vim.keymap.set('n', 'zM', function() require('ufo').closeAllFolds() end)

vim.keymap.set('v', '<leader>p', '"_dP', { desc = "Paste without replacing buffer" })

vim.keymap.set({ 'n', 'v' }, '<Space>', '<Nop>', { silent = true })

vim.keymap.set('n', 'k', "v:count == 0 ? 'gk' : 'k'", { expr = true, silent = true })
vim.keymap.set('n', 'j', "v:count == 0 ? 'gj' : 'j'", { expr = true, silent = true })

vim.keymap.set('n', '<leader>q', vim.diagnostic.setloclist, { desc = 'Open diagnostics list' })

vim.keymap.set('n', '<leader>id', function()
  vim.cmd('normal! o## ' .. os.date('%Y-%m-%d') .. ' ')
  vim.cmd('startinsert!')
end, { desc = '[I]nsert [D]ate heading' })

vim.keymap.set('n', '<leader>it', function()
  vim.cmd('normal! a' .. os.date('%H:%M'))
end, { desc = '[I]nsert [T]ime' })

vim.keymap.set('n', '<leader>iD', function()
  vim.cmd('normal! a' .. os.date('%Y-%m-%d %H:%M'))
end, { desc = '[I]nsert [D]ate and time' })

vim.keymap.set('n', '<leader>ic', function()
  vim.cmd('normal! a- [ ] ')
  vim.cmd('startinsert!')
end, { desc = '[I]nsert [C]heckbox' })

-- signs and the regroup session catch up with a change made outside the buffer
local function touch()
  require('regroup.state').touch()
end

-- the current buffer's file, or nil after saying what could not be done
local function current_file(mod, verb)
  local file = vim.fn.expand(mod)
  if file == '' then
    vim.notify('No file to ' .. verb, vim.log.levels.WARN)
    return nil
  end
  return file
end

local function yank_path(mod)
  local path = current_file(mod, 'copy')
  if not path then return end
  vim.fn.setreg('+', path)
  vim.notify('Copied ' .. path)
end

vim.keymap.set('n', '<leader>fd', function()
  local file = current_file('%:p', 'delete')
  if not file then return end
  if vim.fn.confirm('Delete ' .. file .. '?', '&Yes\n&No', 2) ~= 1 then return end
  vim.fn.delete(file)
  vim.cmd('bdelete!')
end, { desc = '[F]ile [D]elete' })

vim.keymap.set('n', '<leader>fm', function()
  local old = current_file('%:p', 'rename')
  if not old then return end
  -- default = bare filename → same-dir rename; type a path (sub/, ../, ~/, /) to move
  local input = vim.fn.input({ prompt = 'Rename to: ', default = vim.fn.expand('%:t'), completion = 'file' })
  if input == '' then return end

  local new
  if input:match('^[~/]') then
    new = vim.fn.expand(input)
  else
    new = vim.fn.expand('%:p:h') .. '/' .. input
  end
  new = vim.fn.fnamemodify(new, ':p')
  if new == old then return end
  if vim.fn.filereadable(new) == 1 then
    vim.notify(new .. ' already exists', vim.log.levels.ERROR)
    return
  end

  vim.fn.mkdir(vim.fn.fnamemodify(new, ':h'), 'p')
  vim.cmd('saveas ' .. vim.fn.fnameescape(new))
  vim.fn.delete(old)
  for _, b in ipairs(vim.api.nvim_list_bufs()) do
    if b ~= vim.api.nvim_get_current_buf() and vim.api.nvim_buf_get_name(b) == old then
      vim.api.nvim_buf_delete(b, { force = true })
    end
  end
  touch()
  vim.notify('Renamed to ' .. vim.fn.fnamemodify(new, ':~:.'))
end, { desc = '[F]ile [m]ove/rename' })

vim.keymap.set('n', '<leader>fc', function()
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  vim.fn.setreg('+', table.concat(lines, '\n'))
  vim.notify('Copied ' .. #lines .. ' lines to clipboard')
end, { desc = '[F]ile [C]opy contents' })

vim.keymap.set('n', '<leader>fy', function() yank_path('%') end, { desc = '[F]ile relative path [y]ank' })
vim.keymap.set('n', '<leader>fY', function() yank_path('%:p') end, { desc = '[F]ile absolute path [Y]ank' })

vim.keymap.set('n', '<leader>fr', function()
  local file = current_file('%', 'restore')
  if not file then return end
  if vim.fn.confirm('Restore ' .. file .. ' to HEAD? (discards staged + unstaged changes)', '&Yes\n&No', 2) ~= 1 then return end
  vim.cmd('Git restore --source=HEAD --staged --worktree -- ' .. vim.fn.fnameescape(file))
  vim.cmd('edit!')
  touch()
end, { desc = '[F]ile [R]estore to HEAD' })

vim.keymap.set('n', '<leader>gs', ":Git<enter>", { desc = '[G]it [S]tatus' })
vim.keymap.set('n', '<leader>gd', ":Gdiffsplit<enter>", { desc = '[G]it [D]iff' })
vim.keymap.set('n', '<leader>ga', ":Git add %<enter>", { desc = '[G]it [A]dd' })
vim.keymap.set('n', '<leader>gc', ":Git commit -m \"\"<Left>", { desc = '[G]it [C]ommit' })
vim.keymap.set('n', '<leader>gp', ":Git push<enter>", { desc = '[G]it [P]ush' })
vim.keymap.set('n', '<leader>gl', ":Git pull<enter>", { desc = '[G]it Pul[l]' })
vim.keymap.set('n', '<leader>gr', function() require('regroup.review').toggle() end, { desc = 'Toggle Git [R]eview mode' })
vim.keymap.set('n', '<leader>gw', function()
  local msg = vim.fn.input('Commit: ')
  if msg == '' then return end
  vim.cmd('Git add %')
  vim.cmd('Git commit -m ' .. vim.fn.shellescape(msg))
  touch()
end, { desc = '[G]it [W]rite' })
vim.keymap.set("n", "<leader>gh", function()
  local file = vim.fn.expand("%")
  local line = vim.fn.line(".")
  vim.cmd(string.format("Git log -L %d,%d:%s", math.max(1, line - 5), line + 5, file))
end, { desc = "[G]it commit [H]istory (log) for current line" })

require('regroup').setup()

local highlight_group = vim.api.nvim_create_augroup('YankHighlight', { clear = true })
vim.api.nvim_create_autocmd('TextYankPost', {
  callback = function() vim.hl.on_yank() end,
  group = highlight_group,
  pattern = '*',
})

vim.api.nvim_create_autocmd("User", {
  pattern = "FugitiveChanged",
  callback = touch,
})

vim.api.nvim_create_autocmd("OptionSet", {
  pattern = "diff",
  callback = function()
    if vim.wo.diff then
      vim.opt_local.wrap = true
      vim.opt_local.linebreak = true
      vim.opt_local.foldlevel = 0
    else
      vim.opt_local.foldlevel = 99
    end
  end,
})

vim.api.nvim_create_autocmd("OptionSet", {
  pattern = "foldmethod",
  callback = function()
    if vim.wo.diff and vim.v.option_new ~= 'diff' then
      vim.wo.foldmethod = 'diff'
    end
  end,
})

vim.api.nvim_create_autocmd("User", {
  pattern = "TelescopePreviewerLoaded",
  callback = function(args)
    local win = vim.fn.bufwinid(args.buf)
    if win ~= -1 then
      vim.wo[win].wrap = true
      vim.wo[win].linebreak = true
    end
  end,
})

vim.api.nvim_create_autocmd("FocusGained", {
  callback = function() vim.cmd('checktime') end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = { "markdown", "tex", "plaintex", "xml" },
  callback = function()
    vim.opt_local.spell = true
    vim.opt_local.wrap = true
    vim.opt_local.linebreak = true
  end,
})

-- The markdown highlights query sets `conceal_lines` on code fences. With conceallevel>0
-- that forces the highlight query to re-run over the whole buffer on every edit, which
-- costs ~200 ms per keystroke on a few-thousand-line outline. Inline conceal is unaffected.
do
  local parts = {}
  for _, f in ipairs(vim.treesitter.query.get_files('markdown', 'highlights')) do
    table.insert(parts, table.concat(vim.fn.readfile(f), '\n'))
  end
  local src = table.concat(parts, '\n'):gsub('%(#set!%s+conceal_lines%s+""%)', '')
  vim.treesitter.query.set('markdown', 'highlights', src)
end

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
    local max = 500 * 1024
    local ok, stats = pcall(vim.uv.fs_stat, vim.api.nvim_buf_get_name(args.buf))
    if ok and stats and stats.size > max then return end
    pcall(vim.treesitter.start, args.buf, lang)
  end,
})

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

-- as a text object: from visual mode the selection restarts at the cell, from
-- operator-pending mode it becomes the operator's range
local function select_cell()
  local start, stop = get_cell_range()
  if start > stop then return end
  if vim.fn.mode():match('^[vV\22]') then vim.cmd([[execute "normal! \<Esc>"]]) end
  vim.api.nvim_win_set_cursor(0, { start, 0 })
  vim.cmd("normal! V")
  vim.api.nvim_win_set_cursor(0, { stop, 0 })
end

local function molten_evaluate_cell()
  local start, stop = get_cell_range()
  if start > stop then return end
  local view = vim.fn.winsaveview()
  local exec_keys = vim.api.nvim_replace_termcodes(
    string.format("%dGV%dG:<C-u>MoltenEvaluateVisual<CR><Esc>", start, stop),
    true, false, true
  )
  vim.api.nvim_feedkeys(exec_keys, "nx", false)
  vim.schedule(function()
    vim.fn.winrestview(view)
  end)
end

local function molten_insert_cell_separator()
  vim.fn.append(vim.fn.line("."), vim.g.molten_cell_separator)
end

vim.keymap.set({ "x", "o" }, "<leader>mc", select_cell, { silent = true, desc = "molten cell" })
vim.keymap.set("n", "<leader>mm", molten_evaluate_cell, { desc = "evaluate current cell" })
vim.keymap.set("n", "<leader>m-", molten_insert_cell_separator, { desc = "insert cell separator" })

-- vim: ts=2 sts=2 sw=2 et
