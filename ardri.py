#!/usr/bin/env python3
"""Ardri —— 威尔士 tafl 跳棋（规则重构版）。

7x7 棋盘，攻方 16 子围歼，守方 8 子 + 王突围。
王到达任意边缘格守方胜；王被四面围住攻方胜；走子夹吃。

纯标准库：argparse / sys / random / copy。
"""

import argparse
import copy
import random
import sys

SIZE = 7
THRONE = (3, 3)

A = "A"   # 攻方
D = "D"   # 守方
K = "K"   # 王（守方）

DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]

MAX_PLIES = 400  # 半回合上限，撞上限判和棋

PIECE_CN = {"A": "攻", "D": "守", "K": "王"}


def initial_board():
    b = [[None] * SIZE for _ in range(SIZE)]
    b[3][3] = K
    for r, c in [(2, 3), (3, 2), (3, 4), (4, 3),
                 (2, 2), (2, 4), (4, 2), (4, 4)]:
        b[r][c] = D
    for r, c in [(0, 2), (0, 3), (0, 4), (6, 2), (6, 3), (6, 4),
                 (2, 0), (3, 0), (4, 0), (2, 6), (3, 6), (4, 6),
                 (1, 3), (5, 3), (3, 1), (3, 5)]:
        b[r][c] = A
    return b


def in_bounds(r, c):
    return 0 <= r < SIZE and 0 <= c < SIZE


def side_of(piece):
    """棋子属于哪一方：A 或 D（王算守方）。"""
    if piece == A:
        return A
    if piece in (D, K):
        return D
    return None


def is_king(piece):
    return piece == K


class Ardri:
    def __init__(self, board=None, turn=A):
        self.board = board if board is not None else initial_board()
        self.turn = turn          # 'A' 或 'D'
        self.plies = 0
        self._winner = None       # 'A' / 'D' / 'draw' / None

    # ---------- 走法 ----------

    def pieces(self, side):
        out = []
        for r in range(SIZE):
            for c in range(SIZE):
                p = self.board[r][c]
                if p is not None and side_of(p) == side:
                    out.append((r, c))
        return out

    def _slides_from(self, r, c):
        """从 (r,c) 出发的车式走法（不过子）。"""
        moves = []
        for dr, dc in DIRS:
            nr, nc = r + dr, c + dc
            while in_bounds(nr, nc) and self.board[nr][nc] is None:
                # 只有王可以落在王座上
                if (nr, nc) == THRONE and self.board[r][c] != K:
                    break
                moves.append(((r, c), (nr, nc)))
                nr, nc = nr + dr, nc + dc
        return moves

    def legal_moves(self, side=None):
        side = side or self.turn
        moves = []
        for r, c in self.pieces(side):
            moves.extend(self._slides_from(r, c))
        return moves

    def _check_move(self, side, move):
        (fr, fc), (tr, tc) = move
        if not (in_bounds(fr, fc) and in_bounds(tr, tc)):
            raise ValueError(f"走法越界: {move}")
        p = self.board[fr][fc]
        if p is None or side_of(p) != side:
            raise ValueError(f"起点不是己方棋子: {move}")
        if self.board[tr][tc] is not None:
            raise ValueError(f"落点被占: {move}")
        dr, dc = tr - fr, tc - fc
        if (dr != 0 and dc != 0) or (dr == 0 and dc == 0):
            raise ValueError(f"必须横/竖走直线: {move}")
        step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
        step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
        r, c = fr + step_r, fc + step_c
        while (r, c) != (tr, tc):
            if self.board[r][c] is not None:
                raise ValueError(f"路径被挡: {move}")
            if (r, c) == THRONE and p != K:
                raise ValueError(f"非王不可经过王座: {move}")
            r, c = r + step_r, c + step_c
        if (tr, tc) == THRONE and p != K:
            raise ValueError(f"只有王可以占据王座: {move}")

    def apply_move(self, side, move):
        """执行走法，返回吃掉的棋子坐标列表。非法走法抛 ValueError。"""
        if self._winner is not None:
            raise ValueError("对局已结束")
        if side != self.turn:
            raise ValueError(f"轮到 {self.turn} 走")
        self._check_move(side, move)
        (fr, fc), (tr, tc) = move
        piece = self.board[fr][fc]
        self.board[fr][fc] = None
        self.board[tr][tc] = piece
        captured = self._captures_after(piece, tr, tc)
        for r, c in captured:
            self.board[r][c] = None
        self.plies += 1
        self._update_winner()
        if self._winner is None:
            self.turn = D if self.turn == A else A
        return captured

    # ---------- 吃子 ----------

    def _captures_after(self, piece, tr, tc):
        """走子落到 (tr,tc) 后被夹住的敌子（王需四面围，另行判定）。"""
        caps = []
        me = side_of(piece)
        foe = D if me == A else A
        for dr, dc in DIRS:
            nr, nc = tr + dr, tc + dc
            br, bc = tr + 2 * dr, tc + 2 * dc
            if not (in_bounds(nr, nc) and in_bounds(br, bc)):
                continue
            mid = self.board[nr][nc]
            beyond = self.board[br][bc]
            if mid is None or is_king(mid):
                continue
            if side_of(mid) != foe:
                continue
            jaw = False
            if beyond is not None and side_of(beyond) == me:
                jaw = True
            elif (br, bc) == THRONE and beyond is None:
                jaw = True  # 空王座可作夹吃的另一颚
            if jaw:
                caps.append((nr, nc))
        return caps

    def king_pos(self):
        for r in range(SIZE):
            for c in range(SIZE):
                if self.board[r][c] == K:
                    return (r, c)
        return None

    def _king_captured(self):
        kp = self.king_pos()
        if kp is None:
            return True
        kr, kc = kp
        for dr, dc in DIRS:
            nr, nc = kr + dr, kc + dc
            if not in_bounds(nr, nc):
                continue  # 王在边缘=已突围，不会判到这里
            occ = self.board[nr][nc]
            if occ == A:
                continue
            if (nr, nc) == THRONE and occ is None:
                continue  # 空王座视为敌对
            return False
        return True

    def _update_winner(self):
        kp = self.king_pos()
        if kp is None or self._king_captured():
            self._winner = A
            return
        kr, kc = kp
        if kr == 0 or kr == SIZE - 1 or kc == 0 or kc == SIZE - 1:
            self._winner = D
            return
        # 一方无子可走则判负
        if not self.pieces(A):
            self._winner = D
            return
        if not self.pieces(D) and kp is None:
            self._winner = A
            return
        if self.plies >= MAX_PLIES:
            self._winner = "draw"

    def winner(self):
        return self._winner

    def is_over(self):
        return self._winner is not None

    def counts(self):
        na = nd = 0
        for r in range(SIZE):
            for c in range(SIZE):
                p = self.board[r][c]
                if p == A:
                    na += 1
                elif p in (D, K):
                    nd += 1
        return na, nd


# ---------- AI ----------

def evaluate(game):
    """从守方视角打分：正数利好守方。"""
    w = game.winner()
    if w == D:
        return 1e9
    if w == A:
        return -1e9
    if w == "draw":
        return 0.0
    na, nd = game.counts()
    score = (nd - na) * 10.0
    kp = game.king_pos()
    if kp is None:
        return -1e9
    kr, kc = kp
    d_edge = min(kr, SIZE - 1 - kr, kc, SIZE - 1 - kc)
    score += (3 - d_edge) * 30.0          # 王离边缘越近越好（守方）
    adj_a = 0
    for dr, dc in DIRS:
        nr, nc = kr + dr, kc + dc
        if in_bounds(nr, nc) and game.board[nr][nc] == A:
            adj_a += 1
    score -= adj_a * 40.0                # 王身边攻子越少越好
    score += len(game._slides_from(kr, kc)) * 2.0  # 王的机动性
    return score


def ai_choose(game, side, rng):
    moves = game.legal_moves(side)
    if not moves:
        return None
    scored = []
    for mv in moves:
        g2 = copy.deepcopy(game)
        g2.turn = side
        try:
            g2.apply_move(side, mv)
        except ValueError:
            continue
        scored.append((evaluate(g2), mv))
    if not scored:
        return None
    if side == D:
        best = max(s[0] for s in scored)
    else:
        best = min(s[0] for s in scored)
    cands = [mv for s, mv in scored if s == best]
    return rng.choice(cands)


# ---------- 文本界面 ----------

def render(game):
    lines = ["   " + " ".join(str(c) for c in range(SIZE))]
    for r in range(SIZE):
        row = []
        for c in range(SIZE):
            p = game.board[r][c]
            if p is None:
                row.append("·" if (r, c) != THRONE else "○")
            else:
                row.append(PIECE_CN[p])
        lines.append(f"{r}  " + " ".join(row))
    return "\n".join(lines)


def parse_coord(s):
    parts = s.strip().split()
    if len(parts) != 4:
        raise ValueError("请输入 4 个数字：起始行 起始列 目标行 目标列")
    r1, c1, r2, c2 = (int(x) for x in parts)
    if not all(in_bounds(r, c) for r, c in [(r1, c1), (r2, c2)]):
        raise ValueError("坐标越界（0-6）")
    return ((r1, c1), (r2, c2))


def play_interactive(human_side, seed=None):
    rng = random.Random(seed)
    game = Ardri()
    print("Ardri 威尔士跳棋：王走到边缘守方胜，王被四面围住攻方胜。")
    print("走法输入 4 个数字：起始行 起始列 目标行 目标列（0-6），q 退出。")
    print(f"你执{'攻方' if human_side == A else '守方'}，攻方先走。")
    while not game.is_over():
        print()
        print(render(game))
        na, nd = game.counts()
        print(f"攻 {na} 子 / 守 {nd} 子（含王），轮到"
              f"{'攻方' if game.turn == A else '守方'}（第 {game.plies + 1} 手）")
        if game.turn == human_side:
            try:
                s = input("走法> ").strip()
            except EOFError:
                print("\n结束。")
                return
            if s.lower() in ("q", "quit", "退出"):
                print("结束。")
                return
            try:
                mv = parse_coord(s)
                caps = game.apply_move(game.turn, mv)
                if caps:
                    print(f"吃子：{caps}")
            except ValueError as e:
                print(f"非法走法：{e}")
        else:
            mv = ai_choose(game, game.turn, rng)
            if mv is None:
                print("AI 无棋可走。")
                break
            caps = game.apply_move(game.turn, mv)
            print(f"AI 走 {mv[0]} -> {mv[1]}" + (f"，吃子 {caps}" if caps else ""))
    print()
    print(render(game))
    w = game.winner()
    print({"A": "攻方胜！", D: "守方胜！", "draw": "和棋。"}[w])


def play_auto(games, seed=None, verbose=False):
    rng = random.Random(seed)
    res = {"A": 0, D: 0, "draw": 0}
    for i in range(games):
        game = Ardri()
        while not game.is_over():
            mv = ai_choose(game, game.turn, rng)
            if mv is None:
                break
            game.apply_move(game.turn, mv)
        w = game.winner() or "draw"
        res[w] += 1
        if verbose:
            na, nd = game.counts()
            print(f"第 {i + 1}/{games} 局："
                  f"{'攻方胜' if w == 'A' else '守方胜' if w == 'D' else '和棋'}"
                  f"（{game.plies} 半回合，攻 {na} 子/守 {nd} 子）")
    print(f"总计：攻方胜 {res['A']}，守方胜 {res['D']}，和棋 {res['draw']}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ardri 威尔士跳棋（tafl 变体重构版）")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--verbose", action="store_true", help="自动演示打印每局")
    ap.add_argument("--side", choices=["A", "D"], default="D",
                    help="人机对战时人类执哪一方（默认守方）")
    args = ap.parse_args(argv)
    if args.auto:
        play_auto(args.games, seed=args.seed, verbose=args.verbose)
    else:
        if not sys.stdin.isatty():
            print("交互模式需要终端；无头演示请用 --auto。", file=sys.stderr)
            sys.exit(2)
        play_interactive(args.side, seed=args.seed)


if __name__ == "__main__":
    main()
