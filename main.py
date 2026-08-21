import flet as ft
import sqlite3
import os
import random
from pathlib import Path

# ---------- 数据库路径（手机上的路径） ----------
DB_PATH = "/sdcard/Download/knowledge.db"
FAVORITE_DB = "/sdcard/Download/favorites.db"

# ---------- 数据访问类 ----------
class KnowledgeDB:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(f"数据库文件未找到: {DB_PATH}")
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def search(self, query, limit=20, offset=0):
        if not query:
            return []
        self.cursor.execute(
            "SELECT id, title, content, source FROM knowledge_items "
            "WHERE title LIKE ? OR content LIKE ? "
            "LIMIT ? OFFSET ?",
            (f'%{query}%', f'%{query}%', limit, offset)
        )
        return self.cursor.fetchall()

    def get_random_question(self, exclude_ids=None):
        if exclude_ids is None:
            exclude_ids = []
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query = f"SELECT id, title, content FROM knowledge_items WHERE id NOT IN ({placeholders}) ORDER BY RANDOM() LIMIT 1"
            self.cursor.execute(query, exclude_ids)
        else:
            self.cursor.execute("SELECT id, title, content FROM knowledge_items ORDER BY RANDOM() LIMIT 1")
        return self.cursor.fetchone()

    def get_graph_data(self, limit=30):
        self.cursor.execute("SELECT id, title FROM knowledge_items ORDER BY RANDOM() LIMIT ?", (limit,))
        rows = self.cursor.fetchall()
        nodes = []
        edges = []
        for row in rows:
            nodes.append({"id": str(row["id"]), "label": row["title"][:20], "group": 1})
        for i in range(len(nodes)-1):
            edges.append({"from": nodes[i]["id"], "to": nodes[i+1]["id"]})
        return nodes, edges

    def close(self):
        if self.conn:
            self.conn.close()

# ---------- 收藏管理 ----------
def init_favorites():
    conn = sqlite3.connect(FAVORITE_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY,
            title TEXT,
            content TEXT,
            source TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_favorite(item):
    conn = sqlite3.connect(FAVORITE_DB)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO favorites (id, title, content, source)
        VALUES (?, ?, ?, ?)
    ''', (item["id"], item["title"], item["content"], item["source"]))
    conn.commit()
    conn.close()

def remove_favorite(item_id):
    conn = sqlite3.connect(FAVORITE_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favorites WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def get_favorites():
    conn = sqlite3.connect(FAVORITE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, content, source FROM favorites")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "content": r[2], "source": r[3]} for r in rows]

# ---------- Flet 主应用 ----------
class KnowledgeApp:
    def __init__(self):
        self.db = KnowledgeDB()
        self.favorites = get_favorites()
        self.current_results = []
        self.quiz_answered_ids = []
        self.page = None
        self.search_field = None
        self.content_area = None
        self.tabs = None

    def build(self, page: ft.Page):
        self.page = page
        page.title = "知识图谱"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0D1117"
        page.padding = 0

        appbar = ft.AppBar(
            title=ft.Text("知识图谱", size=24, weight=ft.FontWeight.W_300, color="#F0F0F0"),
            center_title=True,
            bgcolor="#161B22",
            elevation=0,
            actions=[
                ft.IconButton(ft.icons.SETTINGS_OUTLINED, on_click=self.show_settings),
            ],
        )

        self.search_field = ft.TextField(
            hint_text="搜索知识...",
            border=ft.InputBorder.UNDERLINE,
            filled=True,
            fill_color="#21262D",
            text_style=ft.TextStyle(color="#F0F0F0", size=16),
            hint_style=ft.TextStyle(color="#8B949E", size=16),
            prefix_icon=ft.icons.SEARCH,
            prefix_icon_color="#58A6FF",
            on_submit=self.on_search,
            expand=True,
        )
        search_btn = ft.IconButton(
            icon=ft.icons.ARROW_FORWARD,
            icon_color="#58A6FF",
            on_click=self.on_search,
        )

        self.tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="搜索", icon=ft.icons.SEARCH),
                ft.Tab(text="图谱", icon=ft.icons.SHARE),
                ft.Tab(text="测验", icon=ft.icons.QUIZ),
                ft.Tab(text="收藏", icon=ft.icons.FAVORITE),
            ],
            on_change=self.tab_changed,
        )

        self.content_area = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        )

        main_content = ft.Column(
            [
                ft.Row([self.search_field, search_btn], spacing=10, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.tabs,
                self.content_area,
            ],
            spacing=10,
            expand=True,
        )

        page.add(
            appbar,
            ft.Container(content=main_content, padding=ft.padding.all(10), expand=True),
        )

        self.tab_changed(None)

    def tab_changed(self, e):
        self.content_area.controls.clear()
        index = self.tabs.selected_index
        if index == 0:
            self.show_search_results()
        elif index == 1:
            self.show_graph()
        elif index == 2:
            self.show_quiz()
        elif index == 3:
            self.show_favorites()
        self.page.update()

    def on_search(self, e):
        query = self.search_field.value.strip()
        if not query:
            self.content_area.controls.clear()
            self.content_area.controls.append(ft.Text("请输入关键词", color="#8B949E"))
            self.page.update()
            return
        results = self.db.search(query, limit=50)
        self.current_results = results
        self.show_search_results()

    def show_search_results(self):
        self.content_area.controls.clear()
        if not self.current_results:
            self.content_area.controls.append(ft.Text("未找到结果", color="#8B949E"))
            self.page.update()
            return
        for row in self.current_results:
            is_fav = any(f["id"] == row["id"] for f in self.favorites)
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(row["title"], weight=ft.FontWeight.BOLD, size=16, color="#F0F0F0"),
                        ft.Text(row["content"][:200] + ("..." if len(row["content"])>200 else ""), size=13, color="#C9D1D9"),
                        ft.Row([
                            ft.Text(f"来源: {row['source'] or '未知'}", size=11, color="#8B949E"),
                            ft.IconButton(
                                icon=ft.icons.FAVORITE if is_fav else ft.icons.FAVORITE_BORDER,
                                icon_size=20,
                                icon_color="#FFD700" if is_fav else "#8B949E",
                                on_click=lambda e, row=row: self.toggle_favorite(row),
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ]),
                    padding=10,
                )
            )
            self.content_area.controls.append(card)
        self.page.update()

    def toggle_favorite(self, item):
        if any(f["id"] == item["id"] for f in self.favorites):
            remove_favorite(item["id"])
        else:
            add_favorite(item)
        self.favorites = get_favorites()
        self.show_search_results()
        self.page.update()

    def show_favorites(self):
        self.content_area.controls.clear()
        favs = get_favorites()
        if not favs:
            self.content_area.controls.append(ft.Text("暂无收藏", color="#8B949E"))
            self.page.update()
            return
        for row in favs:
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(row["title"], weight=ft.FontWeight.BOLD, size=16, color="#F0F0F0"),
                        ft.Text(row["content"][:200] + ("..." if len(row["content"])>200 else ""), size=13, color="#C9D1D9"),
                        ft.Row([
                            ft.Text(f"来源: {row['source'] or '未知'}", size=11, color="#8B949E"),
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                icon_size=20,
                                icon_color="#ef5350",
                                on_click=lambda e, row=row: self.remove_favorite_item(row),
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ]),
                    padding=10,
                )
            )
            self.content_area.controls.append(card)
        self.page.update()

    def remove_favorite_item(self, item):
        remove_favorite(item["id"])
        self.favorites = get_favorites()
        self.show_favorites()
        self.page.update()

    def show_graph(self):
        self.content_area.controls.clear()
        nodes, edges = self.db.get_graph_data(limit=30)
        if not nodes:
            self.content_area.controls.append(ft.Text("图谱数据不足", color="#8B949E"))
            self.page.update()
            return
        grid = ft.GridView(expand=1, max_child_extent=150, spacing=10, run_spacing=10)
        for node in nodes:
            grid.controls.append(
                ft.Container(
                    content=ft.Text(node["label"], color="#F0F0F0", size=14),
                    bgcolor="#21262D",
                    padding=10,
                    border_radius=10,
                    alignment=ft.alignment.center,
                )
            )
        self.content_area.controls.append(ft.Text("知识图谱（节点关系图）", size=18, weight=ft.FontWeight.BOLD, color="#58A6FF"))
        self.content_area.controls.append(grid)
        self.page.update()

    def show_quiz(self):
        self.content_area.controls.clear()
        item = self.db.get_random_question(self.quiz_answered_ids)
        if not item:
            self.content_area.controls.append(ft.Text("🎉 所有题目已答完！", color="#58A6FF"))
            self.page.update()
            return
        self.quiz_question = item
        options = [item["title"][:100]]
        self.db.cursor.execute("SELECT title FROM knowledge_items WHERE id != ? ORDER BY RANDOM() LIMIT 3", (item["id"],))
        others = [row[0][:100] for row in self.db.cursor.fetchall()]
        options.extend(others)
        random.shuffle(options)
        self.quiz_options = options
        self.quiz_answer = item["title"][:100]

        self.content_area.controls.append(ft.Text("📝 知识测验", size=20, weight=ft.FontWeight.BOLD, color="#58A6FF"))
        self.content_area.controls.append(ft.Text(item["title"][:200] + "...", size=16, color="#F0F0F0"))
        self.content_area.controls.append(ft.Text("以下哪个标题更匹配上述描述？", size=14, color="#C9D1D9"))

        for idx, opt in enumerate(options):
            btn = ft.ElevatedButton(
                text=opt,
                on_click=lambda e, idx=idx: self.check_quiz_answer(idx),
                width=300,
            )
            self.content_area.controls.append(btn)
        self.page.update()

    def check_quiz_answer(self, idx):
        selected = self.quiz_options[idx]
        correct = self.quiz_answer
        is_correct = (selected == correct)
        if is_correct:
            self.quiz_answered_ids.append(self.quiz_question["id"])
        self.content_area.controls.clear()
        self.content_area.controls.append(ft.Text("✅ 正确！" if is_correct else "❌ 错误", color="#58A6FF" if is_correct else "#ef5350"))
        self.content_area.controls.append(ft.Text(f"正确答案: {correct}", color="#F0F0F0"))
        self.content_area.controls.append(ft.ElevatedButton("下一题", on_click=lambda e: self.show_quiz()))
        self.page.update()

    def show_settings(self, e):
        dlg = ft.AlertDialog(
            title=ft.Text("设置"),
            content=ft.Text(f"数据库路径: {DB_PATH}\n收藏库路径: {FAVORITE_DB}"),
            actions=[ft.TextButton("确定", on_click=lambda e: self.close_dlg(dlg))],
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def close_dlg(self, dlg):
        dlg.open = False
        self.page.update()

# ---------- 启动 ----------
def main():
    init_favorites()
    try:
        app = KnowledgeApp()
        ft.app(target=app.build)
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == "__main__":
    main()
