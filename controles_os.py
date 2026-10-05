import os
import sys
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

APP_TITLE = "Tech Mania - Controle de OS"

# ✅ Banco em AppData
APP_DIR = os.path.join(os.environ.get("APPDATA", "."), "ControleOS")
os.makedirs(APP_DIR, exist_ok=True)
DB_FILE = os.path.join(APP_DIR, "os_loja.db")

STATUS_LIST = [
    "Aberta",
    "Em análise",
    "Em andamento",
    "Aguardando cliente",
    "Pronta",
    "Entregue",
    "Cancelada",
]

EQUIP_LIST = ["Notebook", "PC", "Impressora"]

# ✅ Lista base de serviços (você pode editar aqui quando quiser)
SERVICOS_PADRAO = [
    ("Formatação", 60.0),
    ("Reparo de dobradiça", 120.0),
    ("Limpeza interna", 50.0),
    ("Troca de HD/SSD (mão de obra)", 80.0),
    ("Instalação de programas", 40.0),
    ("Troca de pasta térmica", 70.0),
]


def get_conn():
    return sqlite3.connect(DB_FILE)


def init_db():
    with get_conn() as conn:
        cur = conn.cursor()

        # Tabela principal de OS
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ordens_servico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_entrada TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                cliente_nome TEXT NOT NULL,
                equipamento_tipo TEXT NOT NULL,
                defeito TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Aberta'
            );
            """
        )

        # Tabela de serviços por OS (1 OS -> N serviços)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS os_servicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                os_id INTEGER NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (os_id) REFERENCES ordens_servico(id) ON DELETE CASCADE
            );
            """
        )

        conn.commit()


def add_os(cliente_nome: str, equipamento_tipo: str, defeito: str) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ordens_servico (cliente_nome, equipamento_tipo, defeito, status)
            VALUES (?, ?, ?, 'Aberta');
            """,
            (cliente_nome.strip(), equipamento_tipo.strip(), defeito.strip()),
        )
        conn.commit()
        return cur.lastrowid


def add_servico(os_id: int, descricao: str, valor: float):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO os_servicos (os_id, descricao, valor) VALUES (?, ?, ?);",
            (os_id, descricao.strip(), float(valor)),
        )
        conn.commit()


def delete_servicos(os_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM os_servicos WHERE os_id=?;", (os_id,))
        conn.commit()


def delete_servico_item(os_id: int, descricao: str, valor: float):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM os_servicos
            WHERE id = (
                SELECT id FROM os_servicos
                WHERE os_id=? AND descricao=? AND valor=?
                ORDER BY id DESC
                LIMIT 1
            );
            """,
            (os_id, descricao, float(valor)),
        )
        conn.commit()


def get_servicos(os_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT descricao, valor
            FROM os_servicos
            WHERE os_id=?
            ORDER BY id ASC;
            """,
            (os_id,),
        )
        return cur.fetchall()


def total_servicos(os_id: int) -> float:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(valor), 0) FROM os_servicos WHERE os_id=?;", (os_id,))
        (total,) = cur.fetchone()
        return float(total or 0)


def list_os(search_text: str = "", status_filter: str = "Todos"):
    q = """
        SELECT id, data_entrada, cliente_nome, equipamento_tipo, defeito, status
        FROM ordens_servico
        WHERE 1=1
    """
    params = []

    if search_text.strip():
        q += " AND (cliente_nome LIKE ? OR CAST(id AS TEXT) LIKE ?)"
        like = f"%{search_text.strip()}%"
        params.extend([like, like])

    if status_filter != "Todos":
        q += " AND status = ?"
        params.append(status_filter)

    q += " ORDER BY id DESC LIMIT 500;"

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(q, params)
        return cur.fetchall()


def update_status(os_id: int, new_status: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE ordens_servico SET status=? WHERE id=?;", (new_status, os_id))
        conn.commit()


def get_os(os_id: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, data_entrada, cliente_nome, equipamento_tipo, defeito, status
            FROM ordens_servico
            WHERE id=?;
            """,
            (os_id,),
        )
        return cur.fetchone()


def wrap_text(text: str, max_chars: int):
    text = text.strip()
    if not text:
        return []
    lines = []
    while len(text) > max_chars:
        cut = text.rfind(" ", 0, max_chars)
        if cut == -1:
            cut = max_chars
        lines.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        lines.append(text)
    return lines


def gerar_pdf_os(row):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader

    os_id, data_entrada, cliente, equip, defeito, status = row

    try:
        dt = datetime.strptime(data_entrada, "%Y-%m-%d %H:%M:%S")
        data_fmt = dt.strftime("%d/%m/%Y %H:%M")
    except:
        data_fmt = data_entrada

    pdf_path = os.path.join(os.path.expanduser("~"), "Documents", f"OS_{os_id:06d}.pdf")

    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4

    # ✅ Logo compatível com PyInstaller
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, "logo.png")
    if os.path.exists(logo_path):
        c.drawImage(ImageReader(logo_path), 220, h - 150, width=150, height=150, mask="auto")

    y = h - 180

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w / 2, y, "TECH MANIA")
    y -= 25

    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, y, "A solução que você procura")
    y -= 25

    c.line(60, y, w - 60, y)
    y -= 25

    c.setFont("Helvetica", 12)
    c.drawString(80, y, f"OS: {os_id:06d}")
    y -= 18
    c.drawString(80, y, f"Entrada: {data_fmt}")
    y -= 18
    c.drawString(80, y, f"Cliente: {cliente}")
    y -= 18
    c.drawString(80, y, f"Equipamento: {equip}")
    y -= 18
    c.drawString(80, y, f"Status: {status}")
    y -= 22

    c.setFont("Helvetica-Bold", 12)
    c.drawString(80, y, "Defeito informado:")
    y -= 16
    c.setFont("Helvetica", 12)
    defeito = (defeito or "").replace("\r", "").strip()
    for line in wrap_text(defeito, 85)[:10]:
        c.drawString(80, y, line)
        y -= 15

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(80, y, "Serviços / Valores:")
    y -= 16
    c.setFont("Helvetica", 12)

    itens = get_servicos(os_id)
    if not itens:
        c.drawString(80, y, "- (não informado)")
        y -= 15
    else:
        for desc, val in itens[:15]:
            c.drawString(80, y, f"- {desc}")
            c.drawRightString(w - 80, y, f"R$ {val:.2f}")
            y -= 15

    total = total_servicos(os_id)
    y -= 10
    c.setFont("Helvetica-Bold", 13)
    c.drawString(80, y, "Total:")
    c.drawRightString(w - 80, y, f"R$ {total:.2f}")
    y -= 20

    c.line(60, y, w - 60, y)
    y -= 20

    c.setFont("Helvetica", 12)
    c.drawCentredString(w / 2, y, "WhatsApp: 79 9 9611-0291")
    y -= 16
    c.drawCentredString(w / 2, y, "Instagram: @tech_mania079")
    y -= 20

    c.setFont("Helvetica-Oblique", 11)
    c.drawCentredString(w / 2, y, "Obrigado pela preferência! Qualquer coisa, chama no WhatsApp 😊")

    c.showPage()
    c.save()
    return pdf_path


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1080x640")
        self.minsize(980, 600)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Nova OS
        frm_new = ttk.LabelFrame(self, text="Nova OS")
        frm_new.pack(fill="x", padx=10, pady=8)

        ttk.Label(frm_new, text="Cliente (nome):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.ent_cliente = ttk.Entry(frm_new, width=35)
        self.ent_cliente.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        ttk.Label(frm_new, text="Equipamento:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.cmb_equip = ttk.Combobox(frm_new, values=EQUIP_LIST, state="readonly", width=18)
        self.cmb_equip.current(0)
        self.cmb_equip.grid(row=0, column=3, padx=6, pady=6, sticky="w")

        ttk.Label(frm_new, text="Defeito:").grid(row=1, column=0, padx=6, pady=6, sticky="nw")
        self.txt_defeito = tk.Text(frm_new, height=3, width=70)
        self.txt_defeito.grid(row=1, column=1, columnspan=3, padx=6, pady=6, sticky="w")

        # Serviços (checkbox)
        frm_srv = ttk.LabelFrame(frm_new, text="Serviços (marque o que foi feito)")
        frm_srv.grid(row=2, column=0, columnspan=4, padx=6, pady=6, sticky="we")
        frm_srv.columnconfigure(0, weight=1)

        self.service_vars = []  # (var, descricao, valor)
        for i, (desc, val) in enumerate(SERVICOS_PADRAO):
            var = tk.BooleanVar(value=False)
            chk = ttk.Checkbutton(
                frm_srv,
                text=f"{desc}  (R$ {val:.2f})",
                variable=var,
                command=self.update_total_preview,
            )
            chk.grid(row=i // 2, column=i % 2, padx=8, pady=4, sticky="w")
            self.service_vars.append((var, desc, val))

        # Outro serviço
        frm_outro = ttk.Frame(frm_new)
        frm_outro.grid(row=3, column=0, columnspan=4, padx=6, pady=(0, 6), sticky="we")

        ttk.Label(frm_outro, text="Outro serviço:").pack(side="left")
        self.ent_outro_desc = ttk.Entry(frm_outro, width=35)
        self.ent_outro_desc.pack(side="left", padx=6)

        ttk.Label(frm_outro, text="Valor (R$):").pack(side="left")
        self.ent_outro_val = ttk.Entry(frm_outro, width=10)
        self.ent_outro_val.pack(side="left", padx=6)

        self.lbl_total = ttk.Label(frm_outro, text="Total selecionado: R$ 0.00")
        self.lbl_total.pack(side="left", padx=12)

        # ✅ botão não estica (1 linha menor)
        btn_add = ttk.Button(frm_new, text="Salvar OS", command=self.on_add)
        btn_add.grid(row=0, column=4, padx=10, pady=6, sticky="n")

        # Filtros
        frm_filters = ttk.Frame(self)
        frm_filters.pack(fill="x", padx=10)

        ttk.Label(frm_filters, text="Buscar (nome ou nº OS):").pack(side="left")
        self.ent_search = ttk.Entry(frm_filters, width=28)
        self.ent_search.pack(side="left", padx=6)
        self.ent_search.bind("<Return>", lambda e: self.refresh())

        ttk.Label(frm_filters, text="Status:").pack(side="left", padx=(10, 0))
        self.cmb_status_filter = ttk.Combobox(frm_filters, values=["Todos"] + STATUS_LIST, state="readonly", width=18)
        self.cmb_status_filter.current(0)
        self.cmb_status_filter.pack(side="left", padx=6)

        ttk.Button(frm_filters, text="Atualizar", command=self.refresh).pack(side="left", padx=6)

        # Tabela
        frm_table = ttk.Frame(self)
        frm_table.pack(fill="both", expand=True, padx=10, pady=8)

        cols = ("id", "data", "cliente", "equip", "defeito", "status", "total")
        self.tree = ttk.Treeview(frm_table, columns=cols, show="headings")

        # ✅ tags para colorir linhas por status
        self.tree.tag_configure("pronta", background="#d7f5d7")
        self.tree.tag_configure("entregue", background="#d9e7ff")
        self.tree.tag_configure("cancelada", background="#ffd6d6")
        self.tree.tag_configure("andamento", background="#fff1c7")

        self.tree.heading("id", text="OS")
        self.tree.heading("data", text="Entrada")
        self.tree.heading("cliente", text="Cliente")
        self.tree.heading("equip", text="Equipamento")
        self.tree.heading("defeito", text="Defeito")
        self.tree.heading("status", text="Status")
        self.tree.heading("total", text="Total (R$)")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("data", width=150, anchor="center")
        self.tree.column("cliente", width=200)
        self.tree.column("equip", width=120, anchor="center")
        self.tree.column("defeito", width=300)
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("total", width=90, anchor="e")

        vsb = ttk.Scrollbar(frm_table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Ações
        frm_actions = ttk.LabelFrame(self, text="Ações na OS selecionada")
        frm_actions.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Label(frm_actions, text="Novo status:").pack(side="left", padx=6, pady=8)
        self.cmb_new_status = ttk.Combobox(frm_actions, values=STATUS_LIST, state="readonly", width=20)
        self.cmb_new_status.current(0)
        self.cmb_new_status.pack(side="left", padx=6, pady=8)

        ttk.Button(frm_actions, text="Alterar status", command=self.on_update_status).pack(side="left", padx=6)

        ttk.Separator(frm_actions, orient="vertical").pack(side="left", fill="y", padx=10, pady=6)
        ttk.Button(frm_actions, text="Abrir OS", command=self.on_open_os).pack(side="left", padx=6)
        ttk.Button(frm_actions, text="Imprimir OS (PDF)", command=self.on_print).pack(side="left", padx=6)

    def update_total_preview(self):
        total = 0.0
        for var, _, val in self.service_vars:
            if var.get():
                total += float(val)

        outro_val_txt = self.ent_outro_val.get().strip().replace(",", ".")
        if outro_val_txt:
            try:
                total += float(outro_val_txt)
            except:
                pass

        self.lbl_total.config(text=f"Total selecionado: R$ {total:.2f}")

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = list_os(
            search_text=self.ent_search.get(),
            status_filter=self.cmb_status_filter.get() or "Todos",
        )

        for r in rows:
            os_id, data_entrada, cliente, equip, defeito, status = r
            defeito_short = (defeito or "").replace("\r", " ").replace("\n", " ").strip()
            if len(defeito_short) > 55:
                defeito_short = defeito_short[:55] + "..."
            total = total_servicos(os_id)

            st = (status or "").strip().lower()
            tag = ""
            if st == "pronta":
                tag = "pronta"
            elif st == "entregue":
                tag = "entregue"
            elif st == "cancelada":
                tag = "cancelada"
            elif st == "em andamento":
                tag = "andamento"

            self.tree.insert(
                "",
                "end",
                values=(os_id, data_entrada, cliente, equip, defeito_short, status, f"{total:.2f}"),
                tags=(tag,) if tag else ()
            )

    def get_selected_os_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0], "values")
        return int(values[0])

    def on_add(self):
        cliente = self.ent_cliente.get().strip()
        equip = self.cmb_equip.get().strip()
        defeito = self.txt_defeito.get("1.0", "end").strip()

        if not cliente:
            messagebox.showwarning("Validação", "Informe o nome do cliente.")
            return
        if not defeito:
            messagebox.showwarning("Validação", "Informe o defeito.")
            return

        os_id = add_os(cliente, equip, defeito)

        marcou_algum = False
        for var, desc, val in self.service_vars:
            if var.get():
                add_servico(os_id, desc, float(val))
                marcou_algum = True

        outro_desc = self.ent_outro_desc.get().strip()
        outro_val_txt = self.ent_outro_val.get().strip().replace(",", ".")
        if outro_desc and outro_val_txt:
            try:
                outro_val = float(outro_val_txt)
                add_servico(os_id, outro_desc, outro_val)
                marcou_algum = True
            except:
                messagebox.showwarning("Valor inválido", "O valor do 'Outro serviço' precisa ser número (ex: 120 ou 120.50).")

        # limpa campos
        self.ent_cliente.delete(0, "end")
        self.txt_defeito.delete("1.0", "end")
        self.ent_outro_desc.delete(0, "end")
        self.ent_outro_val.delete(0, "end")
        for var, _, _ in self.service_vars:
            var.set(False)
        self.update_total_preview()

        self.refresh()
        total = total_servicos(os_id)
        msg = f"OS {os_id:06d} criada com sucesso!\nTotal: R$ {total:.2f}"
        if not marcou_algum:
            msg += "\n\n(Obs: você não marcou nenhum serviço.)"
        messagebox.showinfo("OK", msg)

    def on_update_status(self):
        os_id = self.get_selected_os_id()
        if os_id is None:
            messagebox.showwarning("Seleção", "Selecione uma OS na lista.")
            return

        new_status = self.cmb_new_status.get()
        update_status(os_id, new_status)
        self.refresh()
        messagebox.showinfo("OK", f"Status da OS {os_id:06d} atualizado para '{new_status}'.")

    def on_print(self):
        os_id = self.get_selected_os_id()
        if os_id is None:
            messagebox.showwarning("Seleção", "Selecione uma OS na lista.")
            return

        row = get_os(os_id)
        if not row:
            messagebox.showerror("Erro", "Não encontrei a OS selecionada no banco.")
            return

        try:
            pdf_path = gerar_pdf_os(row)
            os.startfile(pdf_path)
            messagebox.showinfo("PDF Gerado", f"PDF salvo em:\n{pdf_path}")
        except Exception as e:
            messagebox.showerror("Erro", f"Não consegui gerar o PDF.\n\n{e}")

    def on_open_os(self):
        os_id = self.get_selected_os_id()
        if os_id is None:
            messagebox.showwarning("Seleção", "Selecione uma OS na lista.")
            return

        row = get_os(os_id)
        if not row:
            messagebox.showerror("Erro", "Não encontrei a OS selecionada no banco.")
            return

        os_id, data_entrada, cliente, equip, defeito, status = row

        win = tk.Toplevel(self)
        win.title(f"OS {os_id:06d} - Detalhes")
        win.geometry("780x560")
        win.transient(self)
        win.grab_set()

        frm_top = ttk.Frame(win)
        frm_top.pack(fill="x", padx=12, pady=10)

        ttk.Label(frm_top, text=f"OS: {os_id:06d}", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frm_top, text=f"Entrada: {data_entrada}").grid(row=0, column=1, sticky="w", padx=12)
        ttk.Label(frm_top, text=f"Status: {status}").grid(row=0, column=2, sticky="w", padx=12)

        ttk.Label(frm_top, text=f"Cliente: {cliente}").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(frm_top, text=f"Equip.: {equip}").grid(row=1, column=1, sticky="w", padx=12, pady=(8, 0))

        ttk.Label(win, text="Defeito informado:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12)
        txt_def = tk.Text(win, height=4, wrap="word")
        txt_def.pack(fill="x", padx=12, pady=6)
        txt_def.insert("1.0", defeito)
        txt_def.config(state="disabled")

        frm_srv = ttk.LabelFrame(win, text="Serviços desta OS")
        frm_srv.pack(fill="both", expand=True, padx=12, pady=8)

        cols = ("desc", "valor")
        tree_srv = ttk.Treeview(frm_srv, columns=cols, show="headings", height=10)
        tree_srv.heading("desc", text="Serviço")
        tree_srv.heading("valor", text="Valor (R$)")
        tree_srv.column("desc", width=520)
        tree_srv.column("valor", width=140, anchor="e")
        tree_srv.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(frm_srv, orient="vertical", command=tree_srv.yview)
        tree_srv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        frm_add = ttk.LabelFrame(win, text="Adicionar serviços")
        frm_add.pack(fill="x", padx=12, pady=(0, 10))

        vars_local = []
        for i, (desc, val) in enumerate(SERVICOS_PADRAO):
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(frm_add, text=f"{desc} (R$ {val:.2f})", variable=v).grid(
                row=i // 2, column=i % 2, padx=8, pady=4, sticky="w"
            )
            vars_local.append((v, desc, val))

        row_base = (len(SERVICOS_PADRAO) + 1) // 2 + 1
        ttk.Label(frm_add, text="Outro serviço:").grid(row=row_base, column=0, padx=8, pady=6, sticky="w")
        ent_desc = ttk.Entry(frm_add, width=30)
        ent_desc.grid(row=row_base, column=1, padx=6, pady=6, sticky="w")
        ttk.Label(frm_add, text="Valor:").grid(row=row_base, column=2, padx=8, pady=6, sticky="e")
        ent_val = ttk.Entry(frm_add, width=12)
        ent_val.grid(row=row_base, column=3, padx=6, pady=6, sticky="w")

        frm_btn = ttk.Frame(win)
        frm_btn.pack(fill="x", padx=12, pady=(0, 12))

        lbl_total = ttk.Label(frm_btn, text="Total: R$ 0.00", font=("Segoe UI", 10, "bold"))
        lbl_total.pack(side="right")

        def refresh_srv():
            for it in tree_srv.get_children():
                tree_srv.delete(it)
            itens = get_servicos(os_id)
            for d, v in itens:
                tree_srv.insert("", "end", values=(d, f"{float(v):.2f}"))
            lbl_total.config(text=f"Total: R$ {total_servicos(os_id):.2f}")

        def add_selected():
            added = 0
            for v, d, val in vars_local:
                if v.get():
                    add_servico(os_id, d, float(val))
                    v.set(False)
                    added += 1

            od = ent_desc.get().strip()
            ov = ent_val.get().strip().replace(",", ".")
            if od and ov:
                try:
                    add_servico(os_id, od, float(ov))
                    ent_desc.delete(0, "end")
                    ent_val.delete(0, "end")
                    added += 1
                except:
                    messagebox.showwarning("Valor inválido", "Digite um valor válido (ex: 120 ou 120.50).")
                    return

            if added == 0:
                messagebox.showinfo("Nada selecionado", "Marque algum serviço ou preencha 'Outro serviço'.")
                return

            refresh_srv()
            self.refresh()

        def remove_selected():
            sel = tree_srv.selection()
            if not sel:
                messagebox.showwarning("Seleção", "Selecione um serviço para remover.")
                return
            desc, valtxt = tree_srv.item(sel[0], "values")
            try:
                val = float(str(valtxt).replace(",", "."))
            except:
                val = 0.0
            delete_servico_item(os_id, desc, val)
            refresh_srv()
            self.refresh()

        ttk.Button(frm_btn, text="Adicionar selecionados", command=add_selected).pack(side="left")
        ttk.Button(frm_btn, text="Remover serviço selecionado", command=remove_selected).pack(side="left", padx=8)

        refresh_srv()


if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()