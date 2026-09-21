call plug#begin('~/.vim/plugged')
Plug 'gruvbox-community/gruvbox'
Plug 'ojroques/vim-oscyank', {'branch': 'main'}
call plug#end()
" -----------------------------------------------------------------------------
" Color settings
" -----------------------------------------------------------------------------

set background=dark
set termguicolors
let g:gruvbox_contrast_dark = 'hard'
if filereadable(expand('~/.vim/plugged/gruvbox/colors/gruvbox.vim'))
  colorscheme gruvbox
endif
syntax on
"----------------------------------------------------------------------

let mapleader=" "



"==== Using extenstion to make copying work ====
" vim-oscyank: make ALL yanks go to local (Mac) clipboard via OSC52
let g:oscyank_max_length = 200000

" Visual yanks -> OSC52
xmap y <Plug>OSCYankVisual

" Normal yanks (yy, yw, yiw, yG, ...) -> OSC52
nmap y <Plug>OSCYankOperator
nmap yy <Plug>OSCYankLine
"===============================================

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

map 0 ^
map ) $
" Yank to end of line
map Y y$
map P v$p

" Yank/copy/edit words faster
map <leader>y yiw
map <leader>Y yiW
map <leader>p viwp
map <leader>P viWp
map <leader>c ciw
map <leader>C ciW
map <leader>d diw
map <leader>D diW

" Add new line
map <C-n> o <C-c>


set autoindent
set cindent

set tabstop=4
set shiftwidth=4
set expandtab

 
 
"=== Custom lines comment ==========================
" Default comment symbol
let g:comment_symbol = '#'

" Set comment symbol per filetype
autocmd FileType python      let g:comment_symbol = '#'
autocmd FileType javascript  let g:comment_symbol = '//'
autocmd FileType c           let g:comment_symbol = '//'
autocmd FileType cpp         let g:comment_symbol = '//'
autocmd FileType html        let g:comment_symbol = '<!--'
autocmd FileType sh          let g:comment_symbol = '#'

" Ctrl+/ is <C-_> in Vim
" Visual: comment selected lines
vnoremap <silent> <C-_> :<C-u>call CommentLinesVisual()<CR>

" Normal: comment current line
nnoremap <silent> <C-_> :call CommentLineCurrent()<CR>

function! s:comment_symbol()
  return get(g:, 'comment_symbol', '#')
endfunction

function! CommentLinesVisual()
  let l:symbol = s:comment_symbol()
  " prepend comment symbol + space to each selected line
  execute ":'<,'>s/^/" . escape(l:symbol, '/\') . " /"
endfunction

function! CommentLineCurrent()
  let l:symbol = s:comment_symbol()
  " prepend comment symbol + space to current line
  execute "s/^/" . escape(l:symbol, '/\') . " /"
endfunction
"===============================================
