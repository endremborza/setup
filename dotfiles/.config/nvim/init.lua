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

do
  local orig_lsp_start = vim.lsp.start
  vim.lsp.start = function(config, opts)
    opts = opts or {}
    local bufnr = opts.bufnr or vim.api.nvim_get_current_buf()
    local bufname = vim.api.nvim_buf_get_name(bufnr)
    if not bufname:match("^/") then return nil end
    return orig_lsp_start(config, opts)
  end
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
      'nvim-telescope/telescope.nvim',
      'hrsh7th/cmp-nvim-lsp',
    },
    config = function()
      local capabilities = vim.lsp.protocol.make_client_capabilities()
      capabilities = require('cmp_nvim_lsp').default_capabilities(capabilities)
      capabilities = vim.tbl_deep_extend("force", capabilities, {
        workspace = { didChangeWatchedFiles = { dynamicRegistration = false } },
      })

      vim.lsp.config('*', { capabilities = capabilities })

      vim.lsp.config('texlab', {
        settings = {
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
      })

      vim.lsp.config('pyright', {
        settings = {
          python = {
            analysis = {
              exclude = { ".venv", "**/.venv", "**/node_modules" },
            },
          },
        },
      })

      local _rust_root_cache = {}
      vim.lsp.config('rust_analyzer', {
        root_dir = function(bufnr, on_dir)
          local fname = vim.api.nvim_buf_get_name(bufnr)
          if not fname:match("^/") then return end
          local crate = vim.fs.root(fname, { 'Cargo.toml' })
          if crate and _rust_root_cache[crate] then
            on_dir(_rust_root_cache[crate])
            return
          end
          local ws = vim.fs.root(fname, { 'Cargo.lock', 'rust-project.json' })
          local root = ws or crate or vim.fs.root(fname, { '.git' })
          if root then
            if crate then _rust_root_cache[crate] = root end
            on_dir(root)
          end
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
      vim.lsp.set_log_level("WARN")

      local tele = require('telescope.builtin')

      local on_attach = function(_, bufnr)
        local function nmap(keys, func, desc)
          vim.keymap.set('n', keys, func, { buffer = bufnr, desc = 'LSP: ' .. desc })
        end

        nmap('<leader>rn', vim.lsp.buf.rename, '[R]e[n]ame')
        nmap('<leader>ca', vim.lsp.buf.code_action, '[C]ode [A]ction')
        nmap('gd', tele.lsp_definitions, '[G]oto [D]efinition')
        nmap('gr', tele.lsp_references, '[G]oto [R]eferences')
        nmap('gI', tele.lsp_implementations, '[G]oto [I]mplementation')
        nmap('<leader>D', tele.lsp_type_definitions, 'Type [D]efinition')
        nmap('<leader>ds', tele.lsp_document_symbols, '[D]ocument [S]ymbols')
        nmap('<leader>ws', tele.lsp_dynamic_workspace_symbols, '[W]orkspace [S]ymbols')
        nmap('K', vim.lsp.buf.hover, 'Hover Documentation')
        nmap('<C-k>', vim.lsp.buf.signature_help, 'Signature Documentation')
        nmap('gD', vim.lsp.buf.declaration, '[G]oto [D]eclaration')
      end

      vim.api.nvim_create_autocmd("LspAttach", {
        callback = function(args)
          on_attach(vim.lsp.get_client_by_id(args.data.client_id), args.buf)
        end,
      })
    end,
  },
  {
    'hrsh7th/nvim-cmp',
    event = "BufReadPre",
    dependencies = {
      'L3MON4D3/LuaSnip',
      'saadparwaiz1/cmp_luasnip',
      'hrsh7th/cmp-nvim-lsp',
      'rafamadriz/friendly-snippets',
    },
    config = function()
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
        { '<leader>c', group = '[C]ode' },
        { '<leader>d', group = '[D]ocument' },
        { '<leader>g', group = '[G]it' },
        { '<leader>r', group = '[R]ename' },
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
    config = function()
      local ignore_file = vim.fn.expand("~/.config/ignore_patterns")

      local search_flags = {
        "--no-ignore-vcs",
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

      local tele_std = require('telescope.builtin')

      local review_left = nil
      local review_right = nil
      local review_base = "HEAD"

      local function in_review_mode()
        return review_left and review_right
            and vim.api.nvim_win_is_valid(review_left)
            and vim.api.nvim_win_is_valid(review_right)
      end

      local function set_rl_windows()
        local before = {}
        for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do before[w] = true end
        local file_win = vim.api.nvim_get_current_win()
        vim.cmd("Gvdiffsplit " .. review_base)
        local new_win
        for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
          if not before[w] then
            new_win = w; break
          end
        end
        review_left = new_win or vim.api.nvim_get_current_win()
        review_right = file_win
        vim.api.nvim_set_current_win(review_right)
        vim.schedule(function() vim.cmd("diffupdate!") end)
      end

      local function toggle_review()
        if in_review_mode() then
          vim.api.nvim_set_current_win(review_right)
          vim.cmd("only")
          vim.cmd("diffoff")
          review_left = nil
          review_right = nil
          return
        end

        vim.cmd("botright Git")
        vim.cmd("resize 15")
        vim.cmd("normal! G")

        vim.cmd("wincmd k")
        set_rl_windows()
      end

      local function review_file(file)
        if vim.api.nvim_win_is_valid(review_left) then
          vim.api.nvim_win_close(review_left, false)
        end
        vim.api.nvim_set_current_win(review_right)
        vim.cmd("diffoff")
        vim.cmd("edit " .. vim.fn.fnameescape(file))
        set_rl_windows()
      end

      local function open_file(file)
        if not in_review_mode() then
          vim.cmd("edit " .. vim.fn.fnameescape(file))
          return
        end
        review_file(file)
      end

      local function review_changed_file()
        local picker
        if review_base == "HEAD" then
          picker = function(opts)
            tele_std.git_status(opts)
          end
        else
          picker = function(opts)
            tele_std.git_files(vim.tbl_extend("force", opts or {}, {
              git_command = { "git", "diff", "--name-only", review_base }
            }))
          end
        end
        picker({
          attach_mappings = function(prompt_bufnr, map)
            local actions = require("telescope.actions")
            local action_state = require("telescope.actions.state")

            local function select()
              local entry = action_state.get_selected_entry()
              actions.close(prompt_bufnr)
              open_file(entry.value)
            end

            map("i", "<CR>", select)
            map("n", "<CR>", select)
            return true
          end,
        })
      end

      local function pick_review_branch()
        tele_std.git_branches({
          attach_mappings = function(prompt_bufnr, map)
            local actions = require("telescope.actions")
            local action_state = require("telescope.actions.state")

            local function select_branch()
              local entry = action_state.get_selected_entry()
              actions.close(prompt_bufnr)
              review_base = entry.value
            end

            local function select_head()
              actions.close(prompt_bufnr)
              review_base = "HEAD"
            end

            map("i", "<CR>", select_branch)
            map("n", "<CR>", select_branch)
            map("i", "<C-h>", select_head)
            map("n", "<C-h>", select_head)

            return true
          end,
        })
      end

      local function checkout_branch()
        tele_std.git_branches({
          attach_mappings = function(prompt_bufnr, map)
            local actions = require("telescope.actions")
            local action_state = require("telescope.actions.state")

            local function select_branch()
              local entry = action_state.get_selected_entry()
              actions.close(prompt_bufnr)
              vim.cmd("Git checkout " .. entry.value)
            end
            map("i", "<CR>", select_branch)
            map("n", "<CR>", select_branch)
            return true
          end,
        })
      end

      vim.keymap.set("n", "<leader>gf", review_changed_file, { desc = "Review changed [F]ile" })
      vim.keymap.set("n", "<leader>gr", toggle_review, { desc = "Toggle Git [R]eview mode" })
      vim.keymap.set("n", "<leader>gb", pick_review_branch, { desc = "Review [B]asis branch" })
      vim.keymap.set("n", "<leader>go", checkout_branch, { desc = "Check[O]ut Branch" })

      vim.keymap.set('n', '<leader>?', tele_std.oldfiles, { desc = '[?] Find recently opened files' })
      vim.keymap.set('n', '<leader><space>', tele_std.buffers, { desc = '[ ] Find existing buffers' })
      vim.keymap.set('n', '<leader>/', function()
        tele_std.current_buffer_fuzzy_find(require('telescope.themes').get_dropdown {
          winblend = 10,
          previewer = false,
        })
      end, { desc = '[/] Fuzzily search in current buffer' })

      vim.keymap.set('n', '<leader>s/', function()
        tele_std.live_grep { grep_open_files = true, prompt_title = 'Live Grep in Open Files' }
      end, { desc = '[S]earch [/] in Open Files' })
      vim.keymap.set('n', '<leader>ss', tele_std.builtin, { desc = '[S]earch [S]elect Telescope' })
      vim.keymap.set('n', '<leader>sf', tele_std.find_files, { desc = '[S]earch [F]iles' })
      vim.keymap.set('n', '<leader>st', function()
        tele_std.grep_string { search = 'TODO' }
      end, { desc = '[S]earch [T]odo' })
      vim.keymap.set('n', '<leader>sh', tele_std.help_tags, { desc = '[S]earch [H]elp' })
      vim.keymap.set('n', '<leader>sw', tele_std.grep_string, { desc = '[S]earch current [W]ord' })
      vim.keymap.set('n', '<leader>sg', tele_std.live_grep, { desc = '[S]earch by [G]rep' })
      vim.keymap.set('n', '<leader>sd', tele_std.diagnostics, { desc = '[S]earch [D]iagnostics' })
      vim.keymap.set('n', '<leader>sr', tele_std.resume, { desc = '[S]earch [R]esume' })
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
        'nu',
      })
    end,
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
    event = "BufReadPre",
    config = function()
      require("conform").setup({
        formatters_by_ft = {
          lua = { "stylua" },
          python = { "ruff_format" },
          javascript = { "prettierd", "prettier" },
          css = { "prettierd", "prettier" },
        },
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
    "lervag/vimtex",
    ft = { "tex", "plaintex" },
    config = function()
      vim.g.vimtex_view_method = "zathura"
      vim.g.vimtex_compiler_method = "latexmk"
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
      -- optional dependencies:
      -- a completion engine
      --    hrsh7th/nvim-cmp or Saghen/blink.cmp are popular choices
    },
    ---@type lean.Config
    opts = {
      mappings = true,
    }
  },
  {
    "benlubas/molten-nvim",
    version = "^1.0.0",
    build = ":UpdateRemotePlugins",
    cmd = {
      "MoltenInit", "MoltenInfo", "MoltenEvaluateLine", "MoltenReevaluateCell",
      "MoltenRestart", "MoltenEvaluateVisual", "MoltenDelete", "MoltenHideOutput",
      "MoltenShowOutput", "MoltenEnterOutput", "MoltenNext", "MoltenPrev",
    },
    init = function()
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

vim.o.autoread = true
vim.o.updatetime = 250
vim.o.timeoutlen = 300

vim.o.completeopt = 'menuone,noselect'

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

vim.keymap.set('n', '[d', function()
  vim.diagnostic.jump({ count = -1 })
end, { desc = 'Go to previous diagnostic message' })

vim.keymap.set('n', ']d', function()
  vim.diagnostic.jump({ count = 1 })
end, { desc = 'Go to next diagnostic message' })
vim.keymap.set('n', '<leader>e', vim.diagnostic.open_float, { desc = 'Open floating diagnostic message' })
vim.keymap.set('n', '<leader>q', vim.diagnostic.setloclist, { desc = 'Open diagnostics list' })

local function force_refresh_gitsigns()
  local gs = package.loaded.gitsigns
  if gs then pcall(gs.reset_base, true) end
end

vim.keymap.set('n', '<leader>gs', ":Git status<enter>", { desc = '[G]it [S]tatus' })
vim.keymap.set('n', '<leader>gd', ":Gdiffsplit<enter>", { desc = '[G]it [D]iff' })
vim.keymap.set('n', '<leader>ga', ":Git add %<enter>", { desc = '[G]it [A]dd' })
vim.keymap.set('n', '<leader>gc', ":Git commit -m \"\"<Left>", { desc = '[G]it [C]ommit' })
vim.keymap.set('n', '<leader>gp', ":Git push<enter>", { desc = '[G]it [P]ush' })
vim.keymap.set('n', '<leader>gl', ":Git pull<enter>", { desc = '[G]it Pul[l]' })
vim.keymap.set('n', '<leader>gw', function()
  local msg = vim.fn.input('Commit: ')
  if msg == '' then return end
  vim.cmd('Git add %')
  vim.cmd('Git commit -m ' .. vim.fn.shellescape(msg))
  force_refresh_gitsigns()
end, { desc = '[G]it [W]rite' })
vim.keymap.set("n", "<leader>gh", function()
  local file = vim.fn.expand("%")
  local line = vim.fn.line(".")
  local start_line = math.max(0, line - 5)
  local end_line = line + 5
  vim.cmd(string.format("Git log -L %d,%d:%s", start_line, end_line, file))
end, { desc = "[G]it commit [H]istory (log) for current line" })

local highlight_group = vim.api.nvim_create_augroup('YankHighlight', { clear = true })
vim.api.nvim_create_autocmd('TextYankPost', {
  callback = function() vim.highlight.on_yank() end,
  group = highlight_group,
  pattern = '*',
})

vim.api.nvim_create_autocmd("User", {
  pattern = "FugitiveChanged",
  callback = function() force_refresh_gitsigns() end,
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

vim.api.nvim_create_autocmd({ "FocusGained", "BufEnter" }, {
  callback = function()
    vim.cmd('checktime')
    local gs = package.loaded.gitsigns
    if gs then pcall(gs.reset_base) end
  end,
})

vim.api.nvim_create_autocmd("FileType", {
  pattern = "nu",
  callback = function(event) vim.bo[event.buf].commentstring = "#! /usr/bin/env %s" end,
})

vim.api.nvim_create_autocmd("BufWritePre", {
  pattern = "*.xml",
  callback = function()
    local row, col = unpack(vim.api.nvim_win_get_cursor(0))
    local buf = 0
    local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
    local input = table.concat(lines, "\n")

    vim.fn.system("xmllint --noout --nonet -", input)
    if vim.v.shell_error == 0 then return end

    vim.cmd("silent %!xmllint --format -")
    vim.api.nvim_win_set_cursor(0, { row, col })
  end,
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

local function select_cell()
  local start, stop = get_cell_range()
  if start > stop then return end
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

vim.keymap.set("x", "<leader>mc", ":<C-u>lua select_cell()<CR>", { silent = true, desc = "molten cell" })
vim.keymap.set("o", "<leader>mc", select_cell, { silent = true, desc = "molten cell" })
vim.keymap.set("n", "<leader>mm", molten_evaluate_cell, { desc = "evaluate current cell" })
vim.keymap.set("n", "<leader>m-", molten_insert_cell_separator, { desc = "insert cell separator" })

vim.keymap.set("n", "<localleader>mi", ":MoltenInit<CR>", { silent = true, desc = "initialize the plugin" })
vim.keymap.set("n", "<localleader>mf", ":MoltenInfo<CR>", { silent = true, desc = "plugin info" })
vim.keymap.set("n", "<localleader>ml", ":MoltenEvaluateLine<CR>", { silent = true, desc = "evaluate line" })
vim.keymap.set("n", "<localleader>mr", ":MoltenReevaluateCell<CR>", { silent = true, desc = "re-evaluate cell" })
vim.keymap.set("n", "<localleader>m0", ":MoltenRestart<CR>", { silent = true, desc = "restart kernel" })
vim.keymap.set("v", "<localleader>mv", ":<C-u>MoltenEvaluateVisual<CR>gv", { silent = true, desc = "run selection" })
vim.keymap.set("n", "<localleader>md", ":MoltenDelete<CR>", { silent = true, desc = "molten delete cell" })
vim.keymap.set("n", "<localleader>mh", ":MoltenHideOutput<CR>", { silent = true, desc = "hide output" })
vim.keymap.set("n", "<localleader>mo", ":MoltenShowOutput<CR>", { silent = true, desc = "hide output" })
vim.keymap.set("n", "<localleader>ms", ":noautocmd MoltenEnterOutput<CR>", { silent = true, desc = "show/enter output" })
vim.keymap.set("n", "<localleader>mn", ":MoltenNext<CR>", { silent = true, desc = "next cell" })
vim.keymap.set("n", "<localleader>mb", ":MoltenPrev<CR>", { silent = true, desc = "previous cell" })

-- vim: ts=2 sts=2 sw=2 et
