"""
StockAssist Solutions
Asistente de abastecimiento e inventario.
Python + Tkinter + SQLite (biblioteca estándar).
"""

from __future__ import annotations

import sqlite3
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_NAME = "STOCKASSIST SOLUTIONS"
DB_PATH = Path(__file__).with_name("stockassist.db")
DATOS_PATH = Path(__file__).with_name("datos.cvs")

COLOR_SIDEBAR = "#0f172a"
COLOR_SIDEBAR_HOVER = "#1e293b"
COLOR_ACTIVE = "#2563eb"
COLOR_BG = "#f1f5f9"
COLOR_CARD = "#ffffff"
COLOR_TEXT = "#0f172a"
COLOR_MUTED = "#64748b"
COLOR_DANGER = "#dc2626"
COLOR_WARNING = "#d97706"
COLOR_SUCCESS = "#16a34a"
COLOR_INFO = "#0369a1"

UNIDADES = ("Pieza", "Botella", "Lata", "Paquete", "Caja")
COLUMNAS_PRODUCTO = [
    ("nombre", "Producto", 180),
    ("categoria", "Categoría", 120),
    ("marca", "Marca", 110),
    ("presentacion", "Presentación", 110),
    ("stock", "Stock", 60),
    ("min", "Mín.", 50),
    ("max", "Máx.", 50),
    ("costo", "Costo", 70),
    ("precio", "Precio", 70),
    ("proveedor", "Proveedor", 130),
    ("sku", "Código/SKU", 90),
    ("ubicacion", "Ubicación", 110),
    ("estado", "Estado", 100),
]


def dinero(valor: float) -> str:
    return f"${float(valor):,.2f}"


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clasificar_stock(stock: int, stock_minimo: int) -> str:
    if stock <= 0:
        return "AGOTADO"
    if stock <= stock_minimo:
        return "STOCK BAJO"
    return "NORMAL"


def parsear_dinero(texto: str) -> float:
    limpio = texto.replace("$", "").replace(",", "").strip()
    return float(limpio) if limpio else 0.0


def inferir_unidad(presentacion: str) -> str:
    texto = presentacion.lower()
    if "lata" in texto:
        return "Lata"
    if "botella" in texto:
        return "Botella"
    if "paquete" in texto:
        return "Paquete"
    if "caja" in texto:
        return "Caja"
    return "Pieza"


def valores_producto(p) -> tuple:
    return (
        p["nombre"],
        p["categoria"],
        p["marca"] or "",
        p["presentacion"] or "",
        p["stock"],
        p["stock_minimo"],
        p["stock_maximo"],
        dinero(p["costo"] or 0),
        dinero(p["precio"] or 0),
        p["proveedor_nombre"],
        p["sku"] or "",
        p["ubicacion"] or "",
        p["estado"] if "estado" in p.keys() else clasificar_stock(p["stock"], p["stock_minimo"]),
    )


# ---------------------------------------------------------------------------
# PDF con offsets binarios correctos (para que Adobe/Chrome lo abran)
# ---------------------------------------------------------------------------
class SimplePDF:
    PAGE_W = 612
    PAGE_H = 792

    def __init__(self) -> None:
        self.pages: list[list[tuple[int, float, float, str]]] = [[]]

    def _escape(self, texto: str) -> str:
        tabla = str.maketrans(
            {
                "á": "a",
                "é": "e",
                "í": "i",
                "ó": "o",
                "ú": "u",
                "Á": "A",
                "É": "E",
                "Í": "I",
                "Ó": "O",
                "Ú": "U",
                "ñ": "n",
                "Ñ": "N",
                "ü": "u",
                "Ü": "U",
                "¿": "",
                "¡": "",
            }
        )
        limpio = texto.translate(tabla)
        return limpio.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def add_text(self, x: float, y: float, texto: str, size: int = 11) -> None:
        self.pages[-1].append((size, x, y, self._escape(str(texto))))

    def new_page(self) -> None:
        self.pages.append([])

    def save(self, ruta: str) -> None:
        objetos: list[bytes] = []

        def agregar(cuerpo: str | bytes) -> int:
            if isinstance(cuerpo, str):
                cuerpo = cuerpo.encode("latin-1", errors="replace")
            objetos.append(cuerpo)
            return len(objetos)

        catalog_id = agregar(b"<< /Type /Catalog /Pages 2 0 R >>")
        pages_id = agregar(b"<< /Type /Pages /Kids [] /Count 0 >>")
        font_id = agregar(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

        page_ids: list[int] = []
        for page in self.pages:
            lineas = ["BT"]
            for size, x, y, texto in page:
                lineas.append(f"/F1 {size} Tf")
                lineas.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
                lineas.append(f"({texto}) Tj")
            lineas.append("ET")
            stream = "\n".join(lineas).encode("latin-1", errors="replace")
            content_id = agregar(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
            page_id = agregar(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self.PAGE_W} {self.PAGE_H}] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode("ascii")
            )
            page_ids.append(page_id)

        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objetos[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

        salida = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for i, cuerpo in enumerate(objetos, start=1):
            offsets.append(len(salida))
            salida.extend(f"{i} 0 obj\n".encode("ascii"))
            salida.extend(cuerpo)
            if not cuerpo.endswith(b"\n"):
                salida.extend(b"\n")
            salida.extend(b"endobj\n")
        xref = len(salida)
        salida.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
        salida.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            salida.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        salida.extend(
            f"trailer\n<< /Size {len(objetos) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        )
        Path(ruta).write_bytes(bytes(salida))


# ---------------------------------------------------------------------------
# Capa de datos
# ---------------------------------------------------------------------------
class DatabaseManager:
    def __init__(self, ruta: Path = DB_PATH) -> None:
        self.ruta = ruta
        self.conexion = sqlite3.connect(self.ruta)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.execute("PRAGMA foreign_keys = ON")
        self._crear_tablas()
        self._migrar()

    def _crear_tablas(self) -> None:
        self.conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS proveedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL,
                correo TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                precio REAL NOT NULL,
                stock INTEGER NOT NULL,
                stock_minimo INTEGER NOT NULL,
                stock_maximo INTEGER NOT NULL,
                proveedor_id INTEGER NOT NULL,
                marca TEXT DEFAULT '',
                presentacion TEXT DEFAULT '',
                sku TEXT DEFAULT '',
                unidad_medida TEXT DEFAULT 'Pieza',
                costo REAL DEFAULT 0,
                fecha_caducidad TEXT DEFAULT '',
                ubicacion TEXT DEFAULT '',
                FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
            );

            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                producto_id INTEGER,
                producto_nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                stock_anterior INTEGER NOT NULL,
                stock_nuevo INTEGER NOT NULL,
                precio_unitario REAL DEFAULT 0,
                importe REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS cotizaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL UNIQUE,
                fecha TEXT NOT NULL,
                total REAL NOT NULL,
                estado TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cotizacion_detalle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cotizacion_id INTEGER NOT NULL,
                producto_id INTEGER,
                producto_nombre TEXT NOT NULL,
                proveedor_id INTEGER,
                proveedor_nombre TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_unitario REAL NOT NULL,
                subtotal REAL NOT NULL,
                stock_actual INTEGER NOT NULL,
                stock_minimo INTEGER NOT NULL,
                stock_maximo INTEGER NOT NULL,
                FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id)
            );
            """
        )
        self.conexion.commit()

    def _migrar(self) -> None:
        columnas = {fila[1] for fila in self.conexion.execute("PRAGMA table_info(productos)")}
        extras = {
            "marca": "TEXT DEFAULT ''",
            "presentacion": "TEXT DEFAULT ''",
            "sku": "TEXT DEFAULT ''",
            "unidad_medida": "TEXT DEFAULT 'Pieza'",
            "costo": "REAL DEFAULT 0",
            "fecha_caducidad": "TEXT DEFAULT ''",
            "ubicacion": "TEXT DEFAULT ''",
        }
        for nombre, definicion in extras.items():
            if nombre not in columnas:
                self.conexion.execute(f"ALTER TABLE productos ADD COLUMN {nombre} {definicion}")
        cols_mov = {fila[1] for fila in self.conexion.execute("PRAGMA table_info(movimientos)")}
        if "precio_unitario" not in cols_mov:
            self.conexion.execute("ALTER TABLE movimientos ADD COLUMN precio_unitario REAL DEFAULT 0")
        if "importe" not in cols_mov:
            self.conexion.execute("ALTER TABLE movimientos ADD COLUMN importe REAL DEFAULT 0")
        self.conexion.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self.conexion.execute(sql, params)
        self.conexion.commit()
        return cur

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.conexion.execute(sql, params).fetchall()

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conexion.execute(sql, params).fetchone()

    def cerrar(self) -> None:
        self.conexion.close()


class SupplierManager:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def listar(self) -> list[sqlite3.Row]:
        return self.db.fetchall("SELECT * FROM proveedores ORDER BY nombre")

    def obtener(self, proveedor_id: int) -> sqlite3.Row | None:
        return self.db.fetchone("SELECT * FROM proveedores WHERE id = ?", (proveedor_id,))

    def obtener_por_nombre(self, nombre: str) -> sqlite3.Row | None:
        return self.db.fetchone("SELECT * FROM proveedores WHERE nombre = ?", (nombre.strip(),))

    def crear(self, nombre: str, telefono: str, correo: str) -> int:
        cur = self.db.execute(
            "INSERT INTO proveedores (nombre, telefono, correo) VALUES (?, ?, ?)",
            (nombre.strip(), telefono.strip(), correo.strip()),
        )
        return int(cur.lastrowid)

    def obtener_o_crear(self, nombre: str) -> int:
        existe = self.obtener_por_nombre(nombre)
        if existe:
            return int(existe["id"])
        slug = "".join(ch.lower() for ch in nombre if ch.isalnum()) or "proveedor"
        return self.crear(nombre, "555-0000", f"contacto@{slug}.com")

    def actualizar(self, proveedor_id: int, nombre: str, telefono: str, correo: str) -> None:
        if not self.obtener(proveedor_id):
            raise ValueError("El proveedor no existe.")
        self.db.execute(
            "UPDATE proveedores SET nombre = ?, telefono = ?, correo = ? WHERE id = ?",
            (nombre.strip(), telefono.strip(), correo.strip(), proveedor_id),
        )

    def contar(self) -> int:
        fila = self.db.fetchone("SELECT COUNT(*) AS n FROM proveedores")
        return int(fila["n"]) if fila else 0


class InventoryManager:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def _filtro_busqueda(self, busqueda: str) -> tuple[str, tuple]:
        if not busqueda.strip():
            return "", ()
        like = f"%{busqueda.strip()}%"
        sql = (
            " WHERE p.nombre LIKE ? OR p.categoria LIKE ? OR p.marca LIKE ?"
            " OR p.presentacion LIKE ? OR p.sku LIKE ? OR p.ubicacion LIKE ?"
        )
        return sql, (like, like, like, like, like, like)

    def listar(self, busqueda: str = "") -> list[sqlite3.Row]:
        extra, params = self._filtro_busqueda(busqueda)
        sql = f"""
            SELECT p.*, pr.nombre AS proveedor_nombre,
                   CASE
                       WHEN p.stock <= 0 THEN 'AGOTADO'
                       WHEN p.stock <= p.stock_minimo THEN 'STOCK BAJO'
                       ELSE 'NORMAL'
                   END AS estado
            FROM productos p
            JOIN proveedores pr ON pr.id = p.proveedor_id
            {extra}
            ORDER BY p.nombre, p.presentacion
        """
        return self.db.fetchall(sql, params)

    def obtener(self, producto_id: int) -> sqlite3.Row | None:
        return self.db.fetchone(
            """
            SELECT p.*, pr.nombre AS proveedor_nombre
            FROM productos p
            JOIN proveedores pr ON pr.id = p.proveedor_id
            WHERE p.id = ?
            """,
            (producto_id,),
        )

    def crear(self, **datos) -> int:
        self._validar(datos, stock=int(datos["stock"]))
        if datos.get("sku"):
            otro = self.db.fetchone("SELECT id FROM productos WHERE sku = ?", (datos["sku"].strip(),))
            if otro:
                raise ValueError("Ya existe un producto con ese código/SKU.")
        cur = self.db.execute(
            """
            INSERT INTO productos (
                nombre, categoria, precio, stock, stock_minimo, stock_maximo, proveedor_id,
                marca, presentacion, sku, unidad_medida, costo, fecha_caducidad, ubicacion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datos["nombre"].strip(),
                datos["categoria"].strip(),
                float(datos["precio"]),
                int(datos["stock"]),
                int(datos["stock_minimo"]),
                int(datos["stock_maximo"]),
                int(datos["proveedor_id"]),
                datos.get("marca", "").strip(),
                datos.get("presentacion", "").strip(),
                datos.get("sku", "").strip(),
                datos.get("unidad_medida", "Pieza").strip() or "Pieza",
                float(datos.get("costo") or 0),
                datos.get("fecha_caducidad", "").strip(),
                datos.get("ubicacion", "").strip(),
            ),
        )
        return int(cur.lastrowid)

    def actualizar(self, producto_id: int, **datos) -> None:
        producto = self.obtener(producto_id)
        if not producto:
            raise ValueError("El producto no existe.")
        self._validar(datos, stock=int(producto["stock"]))
        sku = datos.get("sku", "").strip()
        if sku:
            otro = self.db.fetchone(
                "SELECT id FROM productos WHERE sku = ? AND id <> ?",
                (sku, producto_id),
            )
            if otro:
                raise ValueError("Ya existe un producto con ese código/SKU.")
        self.db.execute(
            """
            UPDATE productos SET
                nombre = ?, categoria = ?, precio = ?, stock_minimo = ?, stock_maximo = ?,
                proveedor_id = ?, marca = ?, presentacion = ?, sku = ?, unidad_medida = ?,
                costo = ?, fecha_caducidad = ?, ubicacion = ?
            WHERE id = ?
            """,
            (
                datos["nombre"].strip(),
                datos["categoria"].strip(),
                float(datos["precio"]),
                int(datos["stock_minimo"]),
                int(datos["stock_maximo"]),
                int(datos["proveedor_id"]),
                datos.get("marca", "").strip(),
                datos.get("presentacion", "").strip(),
                sku,
                datos.get("unidad_medida", "Pieza").strip() or "Pieza",
                float(datos.get("costo") or 0),
                datos.get("fecha_caducidad", "").strip(),
                datos.get("ubicacion", "").strip(),
                producto_id,
            ),
        )

    def _validar(self, datos: dict, stock: int) -> None:
        if float(datos["precio"]) < 0 or float(datos.get("costo") or 0) < 0:
            raise ValueError("El costo y el precio no pueden ser negativos.")
        if stock < 0 or int(datos["stock_minimo"]) < 0 or int(datos["stock_maximo"]) < 0:
            raise ValueError("El stock no puede ser negativo.")
        if int(datos["stock_maximo"]) < int(datos["stock_minimo"]):
            raise ValueError("El stock máximo no puede ser menor al stock mínimo.")
        if stock > int(datos["stock_maximo"]):
            raise ValueError("El stock actual no puede ser mayor al stock máximo.")
        proveedor = self.db.fetchone("SELECT id FROM proveedores WHERE id = ?", (int(datos["proveedor_id"]),))
        if not proveedor:
            raise ValueError("El proveedor seleccionado no existe.")

    def cambiar_stock(self, producto_id: int, nuevo_stock: int, tipo: str) -> sqlite3.Row:
        producto = self.obtener(producto_id)
        if not producto:
            raise ValueError("El producto no existe.")
        if nuevo_stock < 0:
            raise ValueError("El stock no puede ser negativo.")
        if nuevo_stock > producto["stock_maximo"] and tipo != "AJUSTE":
            raise ValueError("El stock no puede superar el máximo definido.")
        stock_anterior = int(producto["stock"])
        cantidad = abs(nuevo_stock - stock_anterior) if tipo != "AJUSTE" else (nuevo_stock - stock_anterior)
        if tipo == "SALIDA":
            precio_unitario = float(producto["precio"] or 0)
        elif tipo == "ENTRADA":
            precio_unitario = float(producto["costo"] or 0)
        else:
            precio_unitario = 0.0
        importe = abs(cantidad) * precio_unitario
        self.db.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo_stock, producto_id))
        self.db.execute(
            """
            INSERT INTO movimientos
            (fecha, producto_id, producto_nombre, tipo, cantidad, stock_anterior, stock_nuevo, precio_unitario, importe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ahora(), producto_id, producto["nombre"], tipo, cantidad, stock_anterior, nuevo_stock, precio_unitario, importe),
        )
        return self.obtener(producto_id)

    def productos_criticos(self) -> list[sqlite3.Row]:
        return self.db.fetchall(
            """
            SELECT p.*, pr.nombre AS proveedor_nombre
            FROM productos p
            JOIN proveedores pr ON pr.id = p.proveedor_id
            WHERE p.stock <= p.stock_minimo
            ORDER BY pr.nombre, p.nombre
            """
        )

    def indicadores(self) -> dict:
        fila = self.db.fetchone(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN stock <= 0 THEN 1 ELSE 0 END) AS agotados,
                SUM(CASE WHEN stock > 0 AND stock <= stock_minimo THEN 1 ELSE 0 END) AS bajos,
                SUM(stock * COALESCE(costo, 0)) AS valor
            FROM productos
            """
        )
        return {
            "total": int(fila["total"] or 0),
            "agotados": int(fila["agotados"] or 0),
            "bajos": int(fila["bajos"] or 0),
            "valor": float(fila["valor"] or 0),
        }

    def movimientos(self, filtro: str = "TODOS") -> list[sqlite3.Row]:
        sql = "SELECT * FROM movimientos"
        params: tuple = ()
        if filtro == "VENTAS":
            sql += " WHERE tipo = ?"
            params = ("SALIDA",)
        elif filtro == "ENTRADAS":
            sql += " WHERE tipo = ?"
            params = ("ENTRADA",)
        sql += " ORDER BY id DESC"
        return self.db.fetchall(sql, params)

    def total_movimientos(self, filtro: str) -> float:
        if filtro == "VENTAS":
            tipo, campo_producto = "SALIDA", "precio"
        elif filtro == "ENTRADAS":
            tipo, campo_producto = "ENTRADA", "costo"
        else:
            return 0.0
        fila = self.db.fetchone(
            f"""
            SELECT SUM(
                CASE
                    WHEN COALESCE(m.importe, 0) > 0 THEN m.importe
                    ELSE ABS(m.cantidad) * COALESCE(p.{campo_producto}, 0)
                END
            ) AS total
            FROM movimientos m
            LEFT JOIN productos p ON p.id = m.producto_id
            WHERE m.tipo = ?
            """,
            (tipo,),
        )
        return float(fila["total"] or 0)

    def cargar_catalogo_inicial(self, proveedores: SupplierManager) -> int:
        if not DATOS_PATH.exists():
            return 0
        insertados = 0
        for linea in DATOS_PATH.read_text(encoding="utf-8").splitlines():
            if not linea.strip().startswith("|"):
                continue
            if "---" in linea or "Producto" in linea:
                continue
            cols = [c.strip() for c in linea.strip().strip("|").split("|")]
            if len(cols) < 13:
                continue
            try:
                nombre = cols[1]
                categoria = cols[2]
                marca = cols[3]
                presentacion = cols[4]
                stock = int(cols[5])
                minimo = int(cols[6])
                maximo = int(cols[7])
                costo = parsear_dinero(cols[8])
                precio = parsear_dinero(cols[9])
                proveedor_nombre = cols[10]
                sku = cols[11]
                ubicacion = cols[12]
            except (ValueError, IndexError):
                continue
            if sku and self.db.fetchone("SELECT id FROM productos WHERE sku = ?", (sku,)):
                continue
            proveedor_id = proveedores.obtener_o_crear(proveedor_nombre)
            self.crear(
                nombre=nombre,
                categoria=categoria,
                precio=precio,
                stock=stock,
                stock_minimo=minimo,
                stock_maximo=maximo,
                proveedor_id=proveedor_id,
                marca=marca,
                presentacion=presentacion,
                sku=sku,
                unidad_medida=inferir_unidad(presentacion),
                costo=costo,
                fecha_caducidad="",
                ubicacion=ubicacion,
            )
            insertados += 1
        return insertados


class SalesManager:
    def __init__(self, inventario: InventoryManager) -> None:
        self.inventario = inventario

    def registrar_venta(self, producto_id: int, cantidad: int) -> dict:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser un número entero mayor a cero.")
        producto = self.inventario.obtener(producto_id)
        if not producto:
            raise ValueError("El producto no existe.")
        if cantidad > producto["stock"]:
            raise ValueError(f"Stock insuficiente. Disponible: {producto['stock']} unidades.")
        actualizado = self.inventario.cambiar_stock(producto_id, int(producto["stock"]) - cantidad, "SALIDA")
        return {
            "producto": actualizado,
            "estado": clasificar_stock(actualizado["stock"], actualizado["stock_minimo"]),
        }


class QuotationManager:
    def __init__(self, db: DatabaseManager, inventario: InventoryManager) -> None:
        self.db = db
        self.inventario = inventario

    def siguiente_numero(self) -> str:
        fila = self.db.fetchone("SELECT COUNT(*) AS n FROM cotizaciones")
        return f"{int(fila['n']) + 1:05d}"

    def armar_borrador(self) -> dict | None:
        criticos = self.inventario.productos_criticos()
        if not criticos:
            return None
        por_proveedor: dict[str, list[dict]] = defaultdict(list)
        for p in criticos:
            cantidad = int(p["stock_maximo"]) - int(p["stock"])
            if cantidad <= 0:
                continue
            costo = float(p["costo"] or 0)
            item = {
                "producto_id": p["id"],
                "producto_nombre": p["nombre"],
                "presentacion": p["presentacion"] or "",
                "proveedor_id": p["proveedor_id"],
                "proveedor_nombre": p["proveedor_nombre"],
                "cantidad_sugerida": cantidad,
                "cantidad": cantidad,
                "precio_unitario": costo,
                "subtotal": cantidad * costo,
                "stock_actual": int(p["stock"]),
                "stock_minimo": int(p["stock_minimo"]),
                "stock_maximo": int(p["stock_maximo"]),
            }
            por_proveedor[p["proveedor_nombre"]].append(item)
        if not por_proveedor:
            return None
        borrador = {
            "numero": self.siguiente_numero(),
            "fecha": ahora(),
            "grupos": dict(por_proveedor),
            "total": 0.0,
        }
        self.recalcular(borrador)
        return borrador

    def recalcular(self, borrador: dict) -> None:
        total = 0.0
        for items in borrador["grupos"].values():
            for item in items:
                item["cantidad"] = int(item["cantidad"])
                item["subtotal"] = item["cantidad"] * float(item["precio_unitario"])
                total += item["subtotal"]
        borrador["total"] = total

    def guardar(self, borrador: dict, estado: str) -> int:
        self.recalcular(borrador)
        cur = self.db.execute(
            "INSERT INTO cotizaciones (numero, fecha, total, estado) VALUES (?, ?, ?, ?)",
            (borrador["numero"], borrador["fecha"], borrador["total"], estado),
        )
        cotizacion_id = int(cur.lastrowid)
        for items in borrador["grupos"].values():
            for item in items:
                if int(item["cantidad"]) <= 0:
                    continue
                self.db.execute(
                    """
                    INSERT INTO cotizacion_detalle (
                        cotizacion_id, producto_id, producto_nombre, proveedor_id,
                        proveedor_nombre, cantidad, precio_unitario, subtotal,
                        stock_actual, stock_minimo, stock_maximo
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cotizacion_id,
                        item["producto_id"],
                        item["producto_nombre"],
                        item["proveedor_id"],
                        item["proveedor_nombre"],
                        item["cantidad"],
                        item["precio_unitario"],
                        item["subtotal"],
                        item["stock_actual"],
                        item["stock_minimo"],
                        item["stock_maximo"],
                    ),
                )
        return cotizacion_id

    def confirmar(self, borrador: dict) -> None:
        self.recalcular(borrador)
        for items in borrador["grupos"].values():
            for item in items:
                cantidad = int(item["cantidad"])
                if cantidad <= 0:
                    continue
                producto = self.inventario.obtener(item["producto_id"])
                if not producto:
                    raise ValueError(f"El producto '{item['producto_nombre']}' ya no existe.")
                nuevo = int(producto["stock"]) + cantidad
                self.db.execute("UPDATE productos SET stock = ? WHERE id = ?", (nuevo, item["producto_id"]))
                costo = float(item["precio_unitario"] or producto["costo"] or 0)
                self.db.execute(
                    """
                    INSERT INTO movimientos
                    (fecha, producto_id, producto_nombre, tipo, cantidad, stock_anterior, stock_nuevo, precio_unitario, importe)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ahora(),
                        item["producto_id"],
                        producto["nombre"],
                        "ENTRADA",
                        cantidad,
                        int(producto["stock"]),
                        nuevo,
                        costo,
                        cantidad * costo,
                    ),
                )
        self.guardar(borrador, "CONFIRMADA")

    def cancelar(self, borrador: dict) -> None:
        self.guardar(borrador, "CANCELADA")

    def listar(self) -> list[sqlite3.Row]:
        return self.db.fetchall("SELECT * FROM cotizaciones ORDER BY id DESC")

    def exportar_pdf(self, borrador: dict, ruta: str) -> None:
        self.recalcular(borrador)
        pdf = SimplePDF()
        y = 750
        pdf.add_text(50, y, APP_NAME, 18)
        y -= 22
        pdf.add_text(50, y, f"COTIZACION #{borrador['numero']}", 14)
        y -= 18
        pdf.add_text(50, y, f"Fecha: {borrador['fecha']}", 11)
        y -= 28
        for proveedor, items in borrador["grupos"].items():
            activos = [i for i in items if int(i["cantidad"]) > 0]
            if not activos:
                continue
            if y < 140:
                pdf.new_page()
                y = 750
            pdf.add_text(50, y, f"Proveedor: {proveedor}", 12)
            y -= 18
            pdf.add_text(50, y, "Producto", 10)
            pdf.add_text(250, y, "Cantidad", 10)
            pdf.add_text(330, y, "Costo", 10)
            pdf.add_text(430, y, "Subtotal", 10)
            y -= 14
            subtotal_prov = 0.0
            for item in activos:
                if y < 90:
                    pdf.new_page()
                    y = 750
                nombre = f"{item['producto_nombre']} {item.get('presentacion', '')}".strip()
                pdf.add_text(50, y, nombre[:36], 10)
                pdf.add_text(250, y, str(item["cantidad"]), 10)
                pdf.add_text(330, y, dinero(item["precio_unitario"]), 10)
                pdf.add_text(430, y, dinero(item["subtotal"]), 10)
                subtotal_prov += item["subtotal"]
                y -= 14
            pdf.add_text(300, y, "Subtotal proveedor:", 10)
            pdf.add_text(430, y, dinero(subtotal_prov), 10)
            y -= 24
        pdf.add_text(300, y, "TOTAL GENERAL:", 12)
        pdf.add_text(430, y, dinero(borrador["total"]), 12)
        pdf.save(ruta)


# ---------------------------------------------------------------------------
# Interfaz
# ---------------------------------------------------------------------------
class FormularioProveedor(tk.Toplevel):
    def __init__(self, master, titulo: str, datos: dict | None = None) -> None:
        super().__init__(master)
        self.title(titulo)
        self.resizable(False, False)
        self.resultado = None
        self.transient(master)
        self.grab_set()
        marco = ttk.Frame(self, padding=16)
        marco.pack(fill="both", expand=True)
        self.nombre = tk.StringVar(value=(datos or {}).get("nombre", ""))
        self.telefono = tk.StringVar(value=(datos or {}).get("telefono", ""))
        self.correo = tk.StringVar(value=(datos or {}).get("correo", ""))
        for i, (etiqueta, var) in enumerate(
            (("Nombre", self.nombre), ("Teléfono", self.telefono), ("Correo", self.correo))
        ):
            ttk.Label(marco, text=etiqueta).grid(row=i, column=0, sticky="w", pady=4)
            ttk.Entry(marco, textvariable=var, width=36).grid(row=i, column=1, pady=4)
        botones = ttk.Frame(marco)
        botones.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(botones, text="Guardar", command=self._guardar).pack(side="left", padx=4)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="left", padx=4)
        self.wait_window()

    def _guardar(self) -> None:
        if not self.nombre.get().strip() or not self.telefono.get().strip() or not self.correo.get().strip():
            messagebox.showerror("Validación", "Todos los campos son obligatorios.", parent=self)
            return
        self.resultado = {
            "nombre": self.nombre.get().strip(),
            "telefono": self.telefono.get().strip(),
            "correo": self.correo.get().strip(),
        }
        self.destroy()


class FormularioProducto(tk.Toplevel):
    def __init__(self, master, proveedores: list, datos: dict | None = None, editar_stock: bool = True) -> None:
        super().__init__(master)
        self.title("Producto")
        self.resizable(False, False)
        self.resultado = None
        self.transient(master)
        self.grab_set()
        datos = datos or {}
        marco = ttk.Frame(self, padding=16)
        marco.pack(fill="both", expand=True)

        self.vars = {
            "nombre": tk.StringVar(value=str(datos.get("nombre", ""))),
            "categoria": tk.StringVar(value=str(datos.get("categoria", ""))),
            "marca": tk.StringVar(value=str(datos.get("marca", ""))),
            "presentacion": tk.StringVar(value=str(datos.get("presentacion", ""))),
            "sku": tk.StringVar(value=str(datos.get("sku", ""))),
            "unidad_medida": tk.StringVar(value=str(datos.get("unidad_medida", "Pieza") or "Pieza")),
            "ubicacion": tk.StringVar(value=str(datos.get("ubicacion", ""))),
            "fecha_caducidad": tk.StringVar(value=str(datos.get("fecha_caducidad", ""))),
            "costo": tk.StringVar(value="" if datos.get("costo") in (None, "") else str(datos.get("costo"))),
            "precio": tk.StringVar(value="" if datos.get("precio") in (None, "") else str(datos.get("precio"))),
            "stock": tk.StringVar(value=str(datos.get("stock", "0"))),
            "stock_minimo": tk.StringVar(value="" if datos.get("stock_minimo") in (None, "") else str(datos.get("stock_minimo"))),
            "stock_maximo": tk.StringVar(value="" if datos.get("stock_maximo") in (None, "") else str(datos.get("stock_maximo"))),
        }
        nombres = [f"{p['id']} - {p['nombre']}" for p in proveedores]
        self.proveedor = tk.StringVar()
        if datos.get("proveedor_id"):
            for n in nombres:
                if n.startswith(f"{datos['proveedor_id']} -"):
                    self.proveedor.set(n)
                    break
        elif nombres:
            self.proveedor.set(nombres[0])

        campos = [
            ("Nombre", "nombre"),
            ("Categoría", "categoria"),
            ("Marca", "marca"),
            ("Presentación", "presentacion"),
            ("Código/SKU", "sku"),
            ("Ubicación", "ubicacion"),
            ("Fecha de caducidad (AAAA-MM-DD)", "fecha_caducidad"),
            ("Costo de compra", "costo"),
            ("Precio de venta", "precio"),
            ("Stock mínimo", "stock_minimo"),
            ("Stock máximo", "stock_maximo"),
        ]
        if editar_stock:
            campos.insert(9, ("Stock actual", "stock"))

        for i, (etiqueta, clave) in enumerate(campos):
            ttk.Label(marco, text=etiqueta).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(marco, textvariable=self.vars[clave], width=38).grid(row=i, column=1, pady=3)

        fila = len(campos)
        ttk.Label(marco, text="Unidad de medida").grid(row=fila, column=0, sticky="w", pady=3)
        ttk.Combobox(
            marco, textvariable=self.vars["unidad_medida"], values=UNIDADES, state="readonly", width=36
        ).grid(row=fila, column=1, pady=3)
        ttk.Label(marco, text="Proveedor").grid(row=fila + 1, column=0, sticky="w", pady=3)
        ttk.Combobox(marco, textvariable=self.proveedor, values=nombres, state="readonly", width=36).grid(
            row=fila + 1, column=1, pady=3
        )
        botones = ttk.Frame(marco)
        botones.grid(row=fila + 2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(botones, text="Guardar", command=self._guardar).pack(side="left", padx=4)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="left", padx=4)
        self.wait_window()

    def _guardar(self) -> None:
        if not self.vars["nombre"].get().strip() or not self.vars["categoria"].get().strip():
            messagebox.showerror("Validación", "Nombre y categoría son obligatorios.", parent=self)
            return
        if not self.proveedor.get():
            messagebox.showerror("Validación", "Debe seleccionar un proveedor.", parent=self)
            return
        try:
            costo = float(self.vars["costo"].get())
            precio = float(self.vars["precio"].get())
            stock = int(self.vars["stock"].get())
            minimo = int(self.vars["stock_minimo"].get())
            maximo = int(self.vars["stock_maximo"].get())
        except ValueError:
            messagebox.showerror("Validación", "Costo, precio y existencias deben ser numéricos.", parent=self)
            return
        if min(costo, precio, stock, minimo, maximo) < 0:
            messagebox.showerror("Validación", "No se permiten valores negativos.", parent=self)
            return
        if maximo < minimo:
            messagebox.showerror("Validación", "El stock máximo no puede ser menor al mínimo.", parent=self)
            return
        self.resultado = {
            "nombre": self.vars["nombre"].get().strip(),
            "categoria": self.vars["categoria"].get().strip(),
            "marca": self.vars["marca"].get().strip(),
            "presentacion": self.vars["presentacion"].get().strip(),
            "sku": self.vars["sku"].get().strip(),
            "unidad_medida": self.vars["unidad_medida"].get().strip(),
            "ubicacion": self.vars["ubicacion"].get().strip(),
            "fecha_caducidad": self.vars["fecha_caducidad"].get().strip(),
            "costo": costo,
            "precio": precio,
            "stock": stock,
            "stock_minimo": minimo,
            "stock_maximo": maximo,
            "proveedor_id": int(self.proveedor.get().split(" - ", 1)[0]),
        }
        self.destroy()


class MainApplication:
    def __init__(self) -> None:
        self.db = DatabaseManager()
        self.proveedores = SupplierManager(self.db)
        self.inventario = InventoryManager(self.db)
        self.ventas = SalesManager(self.inventario)
        self.cotizaciones = QuotationManager(self.db, self.inventario)
        self.borrador_cotizacion: dict | None = None
        self.inventario.cargar_catalogo_inicial(self.proveedores)

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1280x740")
        self.root.minsize(1080, 660)
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self._salir)

        self._configurar_estilos()
        self._construir_layout()
        self.mostrar_dashboard()
        self._actualizar_alerta_visual()

    def _configurar_estilos(self) -> None:
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("TFrame", background=COLOR_BG)
        estilo.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=("Segoe UI", 10))
        estilo.configure("Title.TLabel", background=COLOR_BG, font=("Segoe UI", 18, "bold"))
        estilo.configure("Subtitle.TLabel", background=COLOR_BG, foreground=COLOR_MUTED, font=("Segoe UI", 10))
        estilo.configure("Treeview", font=("Segoe UI", 9), rowheight=26)
        estilo.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        estilo.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _construir_layout(self) -> None:
        self.sidebar = tk.Frame(self.root, bg=COLOR_SIDEBAR, width=240)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(
            self.sidebar,
            text="STOCKASSIST\nSOLUTIONS",
            bg=COLOR_SIDEBAR,
            fg="white",
            font=("Segoe UI", 14, "bold"),
            justify="center",
            pady=24,
        ).pack(fill="x")
        tk.Label(
            self.sidebar,
            text="Asistente de abastecimiento",
            bg=COLOR_SIDEBAR,
            fg="#94a3b8",
            font=("Segoe UI", 8),
        ).pack(pady=(0, 16))

        self.botones_menu: dict[str, tk.Button] = {}
        self.filas_menu: dict[str, tk.Frame] = {}
        opciones = [
            ("dashboard", "Dashboard"),
            ("venta", "Registrar venta"),
            ("inventario", "Inventario"),
            ("productos", "Productos"),
            ("proveedores", "Proveedores"),
            ("alertas", "Alertas"),
            ("cotizacion", "Generar cotización"),
            ("historial", "Historial"),
            ("salir", "Salir"),
        ]
        for clave, texto in opciones:
            fila = tk.Frame(self.sidebar, bg=COLOR_SIDEBAR)
            fila.pack(fill="x", padx=8, pady=2)
            self.filas_menu[clave] = fila
            comando = self._salir if clave == "salir" else lambda c=clave: self._navegar(c)
            btn = tk.Button(
                fila,
                text=f"  {texto}",
                anchor="w",
                bg=COLOR_SIDEBAR,
                fg="white",
                activebackground=COLOR_SIDEBAR_HOVER,
                activeforeground="white",
                bd=0,
                relief="flat",
                font=("Segoe UI", 11),
                cursor="hand2",
                command=comando,
            )
            btn.pack(side="left", fill="x", expand=True, ipady=8)
            self.botones_menu[clave] = btn
            if clave == "alertas":
                self.punto_alertas = tk.Canvas(
                    fila, width=14, height=14, bg=COLOR_SIDEBAR, highlightthickness=0, bd=0
                )
                self.punto_alertas.pack(side="right", padx=8)

        derecha = tk.Frame(self.root, bg=COLOR_BG)
        derecha.pack(side="left", fill="both", expand=True)
        self.header = ttk.Frame(derecha, padding=(24, 18, 24, 8))
        self.header.pack(fill="x")
        self.titulo = ttk.Label(self.header, text="Dashboard", style="Title.TLabel")
        self.titulo.pack(anchor="w")
        self.subtitulo = ttk.Label(self.header, text="Resumen automático del inventario", style="Subtitle.TLabel")
        self.subtitulo.pack(anchor="w")
        self.contenido = ttk.Frame(derecha, padding=(24, 8, 24, 24))
        self.contenido.pack(fill="both", expand=True)
        self.botones_menu["dashboard"].configure(bg=COLOR_ACTIVE)
        self.filas_menu["dashboard"].configure(bg=COLOR_ACTIVE)

    def _actualizar_alerta_visual(self) -> None:
        kpi = self.inventario.indicadores()
        if kpi["agotados"] > 0:
            color = COLOR_DANGER
        elif kpi["bajos"] > 0:
            color = COLOR_WARNING
        else:
            color = ""
        self.punto_alertas.delete("all")
        fondo = self.filas_menu["alertas"].cget("bg")
        self.punto_alertas.configure(bg=fondo)
        if color:
            self.punto_alertas.create_oval(2, 2, 12, 12, fill=color, outline=color)

    def _navegar(self, clave: str) -> None:
        for k, btn in self.botones_menu.items():
            color = COLOR_ACTIVE if k == clave else COLOR_SIDEBAR
            btn.configure(bg=color)
            self.filas_menu[k].configure(bg=color)
        vistas = {
            "dashboard": self.mostrar_dashboard,
            "venta": self.mostrar_venta,
            "inventario": self.mostrar_inventario,
            "productos": self.mostrar_productos,
            "proveedores": self.mostrar_proveedores,
            "alertas": self.mostrar_alertas,
            "cotizacion": lambda: self.mostrar_cotizacion(nuevo=True),
            "historial": self.mostrar_historial,
        }
        vistas[clave]()
        self._actualizar_alerta_visual()

    def _limpiar(self) -> None:
        for w in self.contenido.winfo_children():
            w.destroy()

    def _tarjeta(self, padre, titulo: str, valor: str, color: str) -> None:
        card = tk.Frame(padre, bg=COLOR_CARD, highlightbackground="#e2e8f0", highlightthickness=1)
        card.pack(side="left", fill="both", expand=True, padx=6)
        tk.Frame(card, bg=color, height=5).pack(fill="x")
        tk.Label(card, text=titulo, bg=COLOR_CARD, fg=COLOR_MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=14, pady=(12, 0)
        )
        tk.Label(card, text=valor, bg=COLOR_CARD, fg=COLOR_TEXT, font=("Segoe UI", 18, "bold")).pack(
            anchor="w", padx=14, pady=(0, 14)
        )

    def _tabla(self, padre, columnas: list[tuple[str, str, int]], altura: int = 16) -> ttk.Treeview:
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True)
        tree = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=altura)
        for cid, texto, ancho in columnas:
            tree.heading(cid, text=texto)
            tree.column(cid, width=ancho, minwidth=50, anchor="w")
        yscroll = ttk.Scrollbar(marco, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(marco, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        tree.tag_configure("AGOTADO", foreground=COLOR_DANGER)
        tree.tag_configure("STOCK BAJO", foreground=COLOR_WARNING)
        tree.tag_configure("NORMAL", foreground=COLOR_SUCCESS)
        return tree

    def mostrar_dashboard(self) -> None:
        self.titulo.config(text="Dashboard")
        self.subtitulo.config(text="Indicadores en tiempo real · el monitoreo se actualiza solo")
        self._limpiar()
        kpi = self.inventario.indicadores()
        fila = ttk.Frame(self.contenido)
        fila.pack(fill="x", pady=(0, 16))
        self._tarjeta(fila, "Total de productos", str(kpi["total"]), COLOR_INFO)
        self._tarjeta(fila, "Stock bajo", str(kpi["bajos"]), COLOR_WARNING)
        self._tarjeta(fila, "Productos agotados", str(kpi["agotados"]), COLOR_DANGER)
        self._tarjeta(fila, "Valor del inventario", dinero(kpi["valor"]), COLOR_SUCCESS)
        self._tarjeta(fila, "Proveedores", str(self.proveedores.contar()), COLOR_ACTIVE)

        encabezado = ttk.Frame(self.contenido)
        encabezado.pack(fill="x", pady=(8, 8))
        canvas = tk.Canvas(encabezado, width=16, height=16, bg=COLOR_BG, highlightthickness=0)
        canvas.pack(side="left", padx=(0, 8))
        if kpi["agotados"] > 0:
            canvas.create_oval(2, 2, 14, 14, fill=COLOR_DANGER, outline=COLOR_DANGER)
        elif kpi["bajos"] > 0:
            canvas.create_oval(2, 2, 14, 14, fill=COLOR_WARNING, outline=COLOR_WARNING)
        else:
            canvas.create_oval(2, 2, 14, 14, fill=COLOR_SUCCESS, outline=COLOR_SUCCESS)
        ttk.Label(encabezado, text="Alertas actuales", font=("Segoe UI", 12, "bold")).pack(side="left")

        tree = self._tabla(
            self.contenido,
            [
                ("producto", "Producto", 180),
                ("presentacion", "Presentación", 110),
                ("stock", "Stock", 70),
                ("minimo", "Mínimo", 70),
                ("ubicacion", "Ubicación", 120),
                ("proveedor", "Proveedor", 160),
                ("estado", "Estado", 110),
            ],
            altura=12,
        )
        criticos = self.inventario.productos_criticos()
        if not criticos:
            tree.insert("", "end", values=("Sin alertas. El inventario está en buen estado.", "", "", "", "", "", ""))
        else:
            for p in criticos:
                estado = clasificar_stock(p["stock"], p["stock_minimo"])
                tree.insert(
                    "",
                    "end",
                    values=(
                        p["nombre"],
                        p["presentacion"] or "",
                        p["stock"],
                        p["stock_minimo"],
                        p["ubicacion"] or "",
                        p["proveedor_nombre"],
                        estado,
                    ),
                    tags=(estado,),
                )

    def mostrar_venta(self) -> None:
        self.titulo.config(text="Registrar venta")
        self.subtitulo.config(text="Busque por nombre, SKU, marca o categoría. El stock se descuenta solo.")
        self._limpiar()
        busqueda = tk.StringVar()
        cantidad = tk.StringVar(value="1")
        seleccionado = {"id": None}
        barra = ttk.Frame(self.contenido)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Buscar:").pack(side="left")
        entrada = ttk.Entry(barra, textvariable=busqueda, width=40)
        entrada.pack(side="left", padx=8)
        tree = self._tabla(self.contenido, [("id", "ID", 50)] + COLUMNAS_PRODUCTO, altura=12)

        def refrescar(*_a) -> None:
            tree.delete(*tree.get_children())
            for p in self.inventario.listar(busqueda.get()):
                tree.insert("", "end", values=(p["id"], *valores_producto(p)), tags=(p["estado"],))

        def al_seleccionar(_e=None) -> None:
            item = tree.selection()
            if item:
                seleccionado["id"] = int(tree.item(item[0], "values")[0])

        def vender() -> None:
            if seleccionado["id"] is None:
                messagebox.showerror("Venta", "Seleccione un producto de la lista.")
                return
            try:
                cant = int(cantidad.get())
                resultado = self.ventas.registrar_venta(seleccionado["id"], cant)
            except ValueError as exc:
                messagebox.showerror("No se pudo registrar la venta", str(exc))
                return
            producto, estado = resultado["producto"], resultado["estado"]
            mensaje = f"Venta registrada. Nuevo stock de '{producto['nombre']}': {producto['stock']}."
            if estado in ("AGOTADO", "STOCK BAJO"):
                messagebox.showwarning("Alerta de inventario", mensaje + f"\n\nEstado: {estado}.")
            else:
                messagebox.showinfo("Venta confirmada", mensaje)
            self._actualizar_alerta_visual()
            refrescar()

        entrada.bind("<KeyRelease>", refrescar)
        tree.bind("<<TreeviewSelect>>", al_seleccionar)
        pie = ttk.Frame(self.contenido)
        pie.pack(fill="x", pady=12)
        ttk.Label(pie, text="Cantidad:").pack(side="left")
        ttk.Entry(pie, textvariable=cantidad, width=8).pack(side="left", padx=8)
        ttk.Button(pie, text="Confirmar venta", style="Accent.TButton", command=vender).pack(side="left")
        refrescar()

    def mostrar_inventario(self) -> None:
        self.titulo.config(text="Inventario")
        self.subtitulo.config(text="Consulta, búsqueda y ajuste de existencias")
        self._limpiar()
        busqueda = tk.StringVar()
        barra = ttk.Frame(self.contenido)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Buscar:").pack(side="left")
        entrada = ttk.Entry(barra, textvariable=busqueda, width=40)
        entrada.pack(side="left", padx=8)
        ttk.Button(barra, text="Ajustar stock", command=lambda: ajustar()).pack(side="left", padx=4)
        ttk.Button(barra, text="Registrar entrada", command=lambda: entrada_manual()).pack(side="left", padx=4)
        tree = self._tabla(self.contenido, [("id", "ID", 50)] + COLUMNAS_PRODUCTO)

        def refrescar(*_a) -> None:
            tree.delete(*tree.get_children())
            for p in self.inventario.listar(busqueda.get()):
                tree.insert("", "end", values=(p["id"], *valores_producto(p)), tags=(p["estado"],))

        def producto_seleccionado():
            item = tree.selection()
            if not item:
                messagebox.showerror("Inventario", "Seleccione un producto.")
                return None
            return int(tree.item(item[0], "values")[0])

        def ajustar() -> None:
            pid = producto_seleccionado()
            if pid is None:
                return
            producto = self.inventario.obtener(pid)
            dialogo = tk.Toplevel(self.root)
            dialogo.title("Ajuste de stock")
            dialogo.transient(self.root)
            dialogo.grab_set()
            ttk.Label(dialogo, text=f"{producto['nombre']}  |  Stock actual: {producto['stock']}").pack(padx=16, pady=10)
            var = tk.StringVar(value=str(producto["stock"]))
            ttk.Entry(dialogo, textvariable=var, width=12).pack()

            def ok() -> None:
                try:
                    self.inventario.cambiar_stock(pid, int(var.get()), "AJUSTE")
                    dialogo.destroy()
                    refrescar()
                    self._actualizar_alerta_visual()
                    messagebox.showinfo("Inventario", "Stock actualizado.")
                except ValueError as exc:
                    messagebox.showerror("Validación", str(exc), parent=dialogo)

            ttk.Button(dialogo, text="Guardar", command=ok).pack(pady=10)

        def entrada_manual() -> None:
            pid = producto_seleccionado()
            if pid is None:
                return
            producto = self.inventario.obtener(pid)
            dialogo = tk.Toplevel(self.root)
            dialogo.title("Registrar entrada")
            dialogo.transient(self.root)
            dialogo.grab_set()
            ttk.Label(dialogo, text=f"Entrada para '{producto['nombre']}'").pack(padx=16, pady=10)
            var = tk.StringVar(value="1")
            ttk.Entry(dialogo, textvariable=var, width=12).pack()

            def ok() -> None:
                try:
                    cant = int(var.get())
                    if cant <= 0:
                        raise ValueError("La cantidad debe ser mayor a cero.")
                    self.inventario.cambiar_stock(pid, int(producto["stock"]) + cant, "ENTRADA")
                    dialogo.destroy()
                    refrescar()
                    self._actualizar_alerta_visual()
                    messagebox.showinfo("Inventario", "Entrada registrada.")
                except ValueError as exc:
                    messagebox.showerror("Validación", str(exc), parent=dialogo)

            ttk.Button(dialogo, text="Registrar", command=ok).pack(pady=10)

        entrada.bind("<KeyRelease>", refrescar)
        refrescar()

    def mostrar_productos(self) -> None:
        self.titulo.config(text="Productos")
        self.subtitulo.config(text="Alta y edición del catálogo")
        self._limpiar()
        barra = ttk.Frame(self.contenido)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="Nuevo producto", command=lambda: crear()).pack(side="left", padx=4)
        ttk.Button(barra, text="Editar seleccionado", command=lambda: editar()).pack(side="left", padx=4)
        tree = self._tabla(self.contenido, [("id", "ID", 50)] + COLUMNAS_PRODUCTO)

        def refrescar() -> None:
            tree.delete(*tree.get_children())
            for p in self.inventario.listar():
                tree.insert("", "end", values=(p["id"], *valores_producto(p)), tags=(p["estado"],))

        def datos_formulario(p) -> dict:
            return {clave: p[clave] for clave in p.keys() if clave != "proveedor_nombre"}

        def crear() -> None:
            if not self.proveedores.listar():
                messagebox.showerror("Productos", "Primero registre al menos un proveedor.")
                return
            form = FormularioProducto(self.root, self.proveedores.listar(), editar_stock=True)
            if not form.resultado:
                return
            try:
                self.inventario.crear(**form.resultado)
                refrescar()
                messagebox.showinfo("Productos", "Producto registrado.")
            except ValueError as exc:
                messagebox.showerror("Validación", str(exc))

        def editar() -> None:
            item = tree.selection()
            if not item:
                messagebox.showerror("Productos", "Seleccione un producto.")
                return
            pid = int(tree.item(item[0], "values")[0])
            p = self.inventario.obtener(pid)
            form = FormularioProducto(self.root, self.proveedores.listar(), datos_formulario(p), editar_stock=False)
            if not form.resultado:
                return
            try:
                self.inventario.actualizar(pid, **form.resultado)
                refrescar()
                messagebox.showinfo("Productos", "Producto actualizado.")
            except ValueError as exc:
                messagebox.showerror("Validación", str(exc))

        refrescar()

    def mostrar_proveedores(self) -> None:
        self.titulo.config(text="Proveedores")
        self.subtitulo.config(text="Registro y edición de proveedores")
        self._limpiar()
        barra = ttk.Frame(self.contenido)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Button(barra, text="Nuevo proveedor", command=lambda: crear()).pack(side="left", padx=4)
        ttk.Button(barra, text="Editar seleccionado", command=lambda: editar()).pack(side="left", padx=4)
        tree = self._tabla(
            self.contenido,
            [("id", "ID", 60), ("nombre", "Nombre", 260), ("telefono", "Teléfono", 180), ("correo", "Correo", 280)],
        )

        def refrescar() -> None:
            tree.delete(*tree.get_children())
            for p in self.proveedores.listar():
                tree.insert("", "end", values=(p["id"], p["nombre"], p["telefono"], p["correo"]))

        def crear() -> None:
            form = FormularioProveedor(self.root, "Nuevo proveedor")
            if form.resultado:
                self.proveedores.crear(**form.resultado)
                refrescar()
                messagebox.showinfo("Proveedores", "Proveedor registrado.")

        def editar() -> None:
            item = tree.selection()
            if not item:
                messagebox.showerror("Proveedores", "Seleccione un proveedor.")
                return
            pid = int(tree.item(item[0], "values")[0])
            p = self.proveedores.obtener(pid)
            form = FormularioProveedor(
                self.root,
                "Editar proveedor",
                {"nombre": p["nombre"], "telefono": p["telefono"], "correo": p["correo"]},
            )
            if form.resultado:
                self.proveedores.actualizar(pid, **form.resultado)
                refrescar()
                messagebox.showinfo("Proveedores", "Proveedor actualizado.")

        refrescar()

    def mostrar_alertas(self) -> None:
        self.titulo.config(text="Alertas")
        self.subtitulo.config(text="Detección automática: AGOTADO, STOCK BAJO o NORMAL")
        self._limpiar()
        tree = self._tabla(
            self.contenido,
            [
                ("producto", "Producto", 180),
                ("presentacion", "Presentación", 110),
                ("sku", "SKU", 80),
                ("stock", "Stock", 70),
                ("minimo", "Mínimo", 70),
                ("maximo", "Máximo", 70),
                ("sugerida", "Reposición sugerida", 140),
                ("ubicacion", "Ubicación", 110),
                ("proveedor", "Proveedor", 150),
                ("estado", "Estado", 100),
            ],
        )
        criticos = self.inventario.productos_criticos()
        if not criticos:
            messagebox.showinfo("Alertas", "No hay alertas. El inventario está en buen estado.")
        for p in criticos:
            estado = clasificar_stock(p["stock"], p["stock_minimo"])
            tree.insert(
                "",
                "end",
                values=(
                    p["nombre"],
                    p["presentacion"] or "",
                    p["sku"] or "",
                    p["stock"],
                    p["stock_minimo"],
                    p["stock_maximo"],
                    max(0, int(p["stock_maximo"]) - int(p["stock"])),
                    p["ubicacion"] or "",
                    p["proveedor_nombre"],
                    estado,
                ),
                tags=(estado,),
            )

    def mostrar_cotizacion(self, nuevo: bool = True) -> None:
        self.titulo.config(text="Generar cotización")
        self.subtitulo.config(
            text="Doble clic en una fila para cambiar la cantidad. El costo es el de compra al proveedor."
        )
        self._limpiar()
        if nuevo or not self.borrador_cotizacion:
            self.borrador_cotizacion = self.cotizaciones.armar_borrador()
        if not self.borrador_cotizacion:
            ttk.Label(
                self.contenido,
                text="El inventario está en buen estado. No se requiere cotización.",
                font=("Segoe UI", 12),
            ).pack(anchor="w")
            return

        self.cotizaciones.recalcular(self.borrador_cotizacion)
        borrador = self.borrador_cotizacion
        ttk.Label(
            self.contenido,
            text=f"COTIZACIÓN #{borrador['numero']}   ·   {borrador['fecha']}   ·   Total: {dinero(borrador['total'])}",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        tree = self._tabla(
            self.contenido,
            [
                ("proveedor", "Proveedor", 150),
                ("producto", "Producto", 180),
                ("presentacion", "Presentación", 110),
                ("stock", "Stock", 60),
                ("min", "Mín.", 50),
                ("max", "Máx.", 50),
                ("sugerida", "Sugerida", 80),
                ("cantidad", "A comprar", 90),
                ("costo", "Costo", 80),
                ("subtotal", "Subtotal", 90),
            ],
            altura=14,
        )
        self._ids_cotizacion = {}
        for proveedor, items in borrador["grupos"].items():
            for item in items:
                iid = tree.insert(
                    "",
                    "end",
                    values=(
                        proveedor,
                        item["producto_nombre"],
                        item.get("presentacion", ""),
                        item["stock_actual"],
                        item["stock_minimo"],
                        item["stock_maximo"],
                        item["cantidad_sugerida"],
                        item["cantidad"],
                        dinero(item["precio_unitario"]),
                        dinero(item["subtotal"]),
                    ),
                )
                self._ids_cotizacion[iid] = item

        def editar_cantidad(_event=None) -> None:
            sel = tree.selection()
            if not sel:
                return
            item = self._ids_cotizacion[sel[0]]
            dialogo = tk.Toplevel(self.root)
            dialogo.title("Modificar cantidad")
            dialogo.transient(self.root)
            dialogo.grab_set()
            ttk.Label(
                dialogo,
                text=f"{item['producto_nombre']} {item.get('presentacion', '')}\nSugerida: {item['cantidad_sugerida']}",
            ).pack(padx=16, pady=10)
            var = tk.StringVar(value=str(item["cantidad"]))
            ttk.Entry(dialogo, textvariable=var, width=12).pack()

            def ok() -> None:
                try:
                    cant = int(var.get())
                    if cant < 0:
                        raise ValueError("La cantidad no puede ser negativa.")
                    cupo = int(item["stock_maximo"]) - int(item["stock_actual"])
                    stock_resultante = int(item["stock_actual"]) + cant
                    if cant > cupo:
                        if not messagebox.askyesno(
                            "Stock máximo superado",
                            f"La cantidad ingresada ({cant}) supera el máximo permitido.\n\n"
                            f"Stock actual: {item['stock_actual']}\n"
                            f"Stock máximo: {item['stock_maximo']}\n"
                            f"Cantidad sugerida: {item['cantidad_sugerida']}\n"
                            f"Stock resultante: {stock_resultante}\n\n"
                            "¿Desea continuar de todos modos?",
                            parent=dialogo,
                        ):
                            return
                    item["cantidad"] = cant
                    dialogo.destroy()
                    self.mostrar_cotizacion(nuevo=False)
                except ValueError as exc:
                    messagebox.showerror("Validación", str(exc), parent=dialogo)

            ttk.Button(dialogo, text="Guardar", command=ok).pack(pady=10)

        tree.bind("<Double-1>", editar_cantidad)
        pie = ttk.Frame(self.contenido)
        pie.pack(fill="x", pady=12)
        ttk.Button(pie, text="Modificar cantidad", command=editar_cantidad).pack(side="left", padx=4)
        ttk.Button(pie, text="Confirmar compra", style="Accent.TButton", command=self._confirmar_compra).pack(
            side="left", padx=4
        )
        ttk.Button(pie, text="Cancelar cotización", command=self._cancelar_compra).pack(side="left", padx=4)
        ttk.Button(pie, text="Exportar PDF", command=self._exportar_pdf).pack(side="left", padx=4)

    def _confirmar_compra(self) -> None:
        if not self.borrador_cotizacion:
            return
        excesos = []
        for items in self.borrador_cotizacion["grupos"].values():
            for item in items:
                cupo = int(item["stock_maximo"]) - int(item["stock_actual"])
                if int(item["cantidad"]) > cupo:
                    excesos.append(
                        f"- {item['producto_nombre']}: comprar {item['cantidad']} "
                        f"(máximo sugerido {item['cantidad_sugerida']})"
                    )
        if excesos and not messagebox.askyesno(
            "Stock máximo superado",
            "Hay cantidades que superarían el stock máximo:\n\n"
            + "\n".join(excesos[:8])
            + "\n\n¿Desea confirmar la compra de todos modos?",
        ):
            return
        if not messagebox.askyesno("Confirmar compra", "¿Desea confirmar esta compra?"):
            return
        try:
            self.cotizaciones.confirmar(self.borrador_cotizacion)
        except ValueError as exc:
            messagebox.showerror("Cotización", str(exc))
            return
        messagebox.showinfo("Compra confirmada", "El inventario se actualizó y la cotización quedó registrada.")
        self.borrador_cotizacion = None
        self._navegar("dashboard")

    def _cancelar_compra(self) -> None:
        if not self.borrador_cotizacion:
            return
        if not messagebox.askyesno("Cancelar", "¿Desea cancelar esta cotización? El inventario no se modificará."):
            return
        self.cotizaciones.cancelar(self.borrador_cotizacion)
        self.borrador_cotizacion = None
        messagebox.showinfo("Cotización", "Cotización cancelada. No se registraron entradas.")
        self.mostrar_cotizacion(nuevo=True)

    def _exportar_pdf(self) -> None:
        if not self.borrador_cotizacion:
            messagebox.showerror("PDF", "No hay una cotización para exportar.")
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"cotizacion_{self.borrador_cotizacion['numero']}.pdf",
        )
        if not ruta:
            return
        try:
            self.cotizaciones.exportar_pdf(self.borrador_cotizacion, ruta)
        except OSError as exc:
            messagebox.showerror("PDF", f"No se pudo guardar el archivo:\n{exc}")
            return
        messagebox.showinfo("PDF", f"Cotización guardada en:\n{ruta}")

    def mostrar_historial(self) -> None:
        self.titulo.config(text="Historial")
        self.subtitulo.config(text="Filtre movimientos: todos, solo ventas o solo entradas")
        self._limpiar()
        notebook = ttk.Notebook(self.contenido)
        notebook.pack(fill="both", expand=True)
        tab_mov = ttk.Frame(notebook, padding=8)
        tab_cot = ttk.Frame(notebook, padding=8)
        notebook.add(tab_mov, text="Movimientos")
        notebook.add(tab_cot, text="Cotizaciones")

        filtro = tk.StringVar(value="TODOS")
        barra = ttk.Frame(tab_mov)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Mostrar:").pack(side="left")
        for texto, valor in (("Todos", "TODOS"), ("Solo ventas", "VENTAS"), ("Solo entradas", "ENTRADAS")):
            ttk.Radiobutton(barra, text=texto, value=valor, variable=filtro, command=lambda: refrescar_mov()).pack(
                side="left", padx=8
            )
        lbl_total = ttk.Label(barra, text="", font=("Segoe UI", 10, "bold"))
        lbl_total.pack(side="right")

        tree_m = self._tabla(
            tab_mov,
            [
                ("fecha", "Fecha", 150),
                ("producto", "Producto", 220),
                ("tipo", "Tipo", 90),
                ("cantidad", "Cantidad", 90),
                ("anterior", "Stock anterior", 110),
                ("nuevo", "Stock nuevo", 110),
            ],
        )

        def refrescar_mov() -> None:
            tree_m.delete(*tree_m.get_children())
            modo = filtro.get()
            for m in self.inventario.movimientos(modo):
                tree_m.insert(
                    "",
                    "end",
                    values=(
                        m["fecha"],
                        m["producto_nombre"],
                        m["tipo"],
                        m["cantidad"],
                        m["stock_anterior"],
                        m["stock_nuevo"],
                    ),
                )
            if modo == "VENTAS":
                lbl_total.config(text=f"Total de ventas: {dinero(self.inventario.total_movimientos('VENTAS'))}")
            elif modo == "ENTRADAS":
                lbl_total.config(text=f"Total gastado: {dinero(self.inventario.total_movimientos('ENTRADAS'))}")
            else:
                lbl_total.config(text="")

        refrescar_mov()
        tree_c = self._tabla(
            tab_cot,
            [
                ("numero", "Número", 100),
                ("fecha", "Fecha", 160),
                ("total", "Total", 120),
                ("estado", "Estado", 120),
            ],
        )
        for c in self.cotizaciones.listar():
            tree_c.insert("", "end", values=(c["numero"], c["fecha"], dinero(c["total"]), c["estado"]))

    def _salir(self) -> None:
        if messagebox.askyesno("Salir", "¿Desea cerrar StockAssist Solutions?"):
            self.db.cerrar()
            self.root.destroy()

    def ejecutar(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = MainApplication()
    app.ejecutar()


if __name__ == "__main__":
    main()
