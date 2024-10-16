import curses
import requests

API_URL = "http://localhost:5000"

def get_order_details(order_id):
    response = requests.get(f"{API_URL}/order/{order_id}")
    if response.status_code == 200:
        return response.json()
    else:
        return {"name": f"Order {order_id}", "completed": False}


def view_tasks_curses(stdscr, tasks):
    # 关闭光标显示
    curses.curs_set(0)
    path = tasks['path']
    
    # 获取订单详细信息
    orders = [get_order_details(order_id) for order_id in path]

    # 初始化颜色对
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)

    current_row = 0
    current_page = 0
    items_per_page = 10

    # 设置窗口大小
    height, width = stdscr.getmaxyx()
    window_height = min(height, 50)  # 设置窗口高度为50，或终端高度
    window_width = min(width, 100)  # 设置窗口宽度为100，或终端宽度
    def draw_menu(stdscr, current_row, current_page):
        stdscr.clear()
        start_idx = current_page * items_per_page
        end_idx = start_idx + items_per_page
        max_name_length = max(len(str(item["order_id"])) for item in orders) + 10  # 预留空间
        for idx, item in enumerate(orders[start_idx:end_idx]):
            x = 0
            y = idx + 4  # 向下移动四行
            display_text = f"订单ID: {item['order_id']}"
            if item["status"] == "completed":
                display_text = "(已完成) " + display_text
            if idx == current_row:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, display_text)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, display_text)
        # 显示页号
        stdscr.addstr(items_per_page + 5, 0, f"页号: {current_page + 1}/{(len(orders) - 1) // items_per_page + 1}")
        stdscr.refresh()

    def draw_item_detail(stdscr, item):
        stdscr.clear()
        stdscr.addstr(2, 0, f"订单ID: {item['order_id']}")
        stdscr.addstr(3, 0, f"包裹ID: {item['package_id']}")
        stdscr.addstr(4, 0, f"优先级: {item['priority']}")
        stdscr.addstr(5, 0, f"发件人: {item['sender_name']}")
        stdscr.addstr(6, 0, f"发件地址: {item['sender_address']}")
        stdscr.addstr(7, 0, f"收件人: {item['receiver_name']}")
        stdscr.addstr(8, 0, f"收件地址: {item['receiver_address']}")
        stdscr.addstr(9, 0, f"状态: {item['status']}")
        stdscr.addstr(10, 0, "历史记录:")
        for idx, history in enumerate(item['history'], start=11):
            stdscr.addstr(idx, 0, f"  - {history[0]}: {history[1]}")
        stdscr.addstr(idx + 1, 0, "按 'c' 标记为已完成")
        stdscr.addstr(idx + 2, 0, "按 'b' 返回")
        stdscr.refresh()

    while True:
        draw_menu(stdscr, current_row, current_page)
        key = stdscr.getch()

        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < items_per_page - 1 and current_row < len(orders) - 1:
            current_row += 1
        elif key == curses.KEY_LEFT and current_page > 0:
            current_page -= 1
            current_row = 0
        elif key == curses.KEY_RIGHT and (current_page + 1) * items_per_page < len(orders):
            current_page += 1
            current_row = 0
        elif key == curses.KEY_ENTER or key in [10, 13]:
            while True:
                draw_item_detail(stdscr, orders[current_page * items_per_page + current_row])
                key = stdscr.getch()
                if key == ord('c'):
                    orders[current_page * items_per_page + current_row]["status"] = "completed"
                    draw_item_detail(stdscr, orders[current_page * items_per_page + current_row])  # 重新绘制详细信息页面
                    # 更新订单状态
                    response = requests.put(f"{API_URL}/order/{orders[current_page * items_per_page + current_row]["order_id"]}", json={"status": "completed"})
                elif key == ord('b'):
                    break
            draw_menu(stdscr, current_row, current_page)  # 返回主菜单时重新绘制