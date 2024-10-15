import curses

def main(stdscr):
    # 关闭光标显示
    curses.curs_set(0)

    # 初始化颜色对
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)

    # 示例数据
    items = ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]
    current_row = 0

    while True:
        stdscr.clear()

        # 绘制菜单
        for idx, item in enumerate(items):
            x = 0
            y = idx
            if idx == current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, item)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, item)

        stdscr.refresh()

        # 获取用户输入
        key = stdscr.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(items) - 1:
            current_row += 1
        elif key == ord('q'):
            break

if __name__ == "__main__":
    curses.wrapper(main)