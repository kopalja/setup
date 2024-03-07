
" Install missing plugins   
let data_dir = has('nvim') ? stdpath('data') . '/site' : '~/.vim'
if empty(glob(data_dir . '/autoload/plug.vim'))
  silent execute '!curl -fLo '.data_dir.'/autoload/plug.vim --create-dirs  https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim'
  autocmd VimEnter * PlugInstall --sync | source $MYVIMRC          
endif

call plug#begin('~/.config/nvim/plugged')
Plug 'gruvbox-community/gruvbox'
call plug#end()
" -----------------------------------------------------------------------------
" Color settings
" -----------------------------------------------------------------------------

" Enable 24-bit true colors if your terminal supports it.
if (has("termguicolors"))
  " https://github.com/vim/vim/issues/993#issuecomment-255651605
  let &t_8f = "\<Esc>[38;2;%lu;%lu;%lum"
  let &t_8b = "\<Esc>[48;2;%lu;%lu;%lum"

  set termguicolors
endif

" Enable syntax highlighting.
syntax on

" Specific colorscheme settings (must come before setting your colorscheme).
if !exists('g:gruvbox_contrast_light')
  let g:gruvbox_contrast_light='hard'
endif

" Set the color scheme.
colorscheme gruvbox
set background=dark

" Specific colorscheme settings (must come after setting your colorscheme).
if (g:colors_name == 'gruvbox')
  if (&background == 'dark')
    hi Visual cterm=NONE ctermfg=NONE ctermbg=237 guibg=#3a3a3a
  else
    hi Visual cterm=NONE ctermfg=NONE ctermbg=228 guibg=#f2e5bc
    hi CursorLine cterm=NONE ctermfg=NONE ctermbg=228 guibg=#f2e5bc
    hi ColorColumn cterm=NONE ctermfg=NONE ctermbg=228 guibg=#f2e5bc
  endif
endif
"----------------------------------------------------------------------

let mapleader=" "


" Set system clipboard
set clipboard=unnamedplus

" Change cursor in insert mode
let &t_SI = "\e[5 q"
let &t_EI = "\e[0 q"

" turn relative line numbers on
:set number relativenumber
:set nu rnu

" Dont overdire clipboard with x and X
noremap x "_x
noremap X "_x
xnoremap p pgvy


" Scroll faster
map <C-j> 2j
map <C-k> 2k
map <C-h> 2h
map <C-l> 2l



" Highlight search
set incsearch

" Jump to next with zz
nnoremap n nzz
nnoremap N Nzz

" Yank to end of line
map Y y$
map P v$p
map 0 ^

" Yank/copy/edit words faster
map <leader>y yiw
map <leader>Y yiW
map <leader>p viwp
map <leader>P viWp
map <leader>c ciw
map <leader>C ciW

" Add new line
map <C-n> o <C-c>


set autoindent
set cindent

set tabstop=4
set shiftwidth=4
set expandtab

