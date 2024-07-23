import os
from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form, status, Depends
import pyodbc
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import shutil
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import bcrypt
from typing import List, Dict

app = FastAPI()

server = os.getenv('inovabyte2.database.windows.net')
database = os.getenv('Inovabyte2')
username = os.getenv('geovanydominguez')
password = os.getenv('Flacodeoro55')

# Configuración de CORS para permitir el origen específico y credenciales
origins = [
    "http://127.0.0.1:5500",  # Reemplaza con la URL exacta de tu frontend
    "http://127.0.0.1:52727",
    "http://127.0.0.1:60642",
    "https://geovany-dotcom.github.io/Pagina-Web23/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Ajusta según los métodos que necesites permitir
    allow_headers=["*"],  # Puedes limitar las cabeceras específicas si es necesario
)

if username and password:
    conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
else:
    conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes'

# Prueba de conexión
try:
    conn = pyodbc.connect(conn_str)
    print("Connection successful")
except Exception as e:
    print(f"Connection failed: {e}")

@app.get("/")
def read_root():
    return {"Hello": "World"}

def ejecutar_consulta(query, params=None):
    with pyodbc.connect(conn_str) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            return rows
        else:
            conn.commit()
            return True

def registrar_auditoria(tipo_operacion, tabla, registro_id, usuario):
    query = """
    INSERT INTO AuditoriaCRUD (TipoOperacion, Tabla, RegistroID, Usuario)
    VALUES (?, ?, ?, ?);
    """
    params = (tipo_operacion, tabla, registro_id, usuario)
    ejecutar_consulta(query, params)
    
    

class ClienteCreate(BaseModel):
    nombre: str
    apellido: str
    correo_electronico: EmailStr
    nombre_usuario: str
    contrasena: str

class LoginRequest(BaseModel):
    nombre_usuario: str
    contrasena: str
    
# Modelo Pydantic para la solicitud de cierre de sesión


class LoginResponse(BaseModel):
    mensaje: str
    tipo_usuario: Optional[str] = None

class Producto(BaseModel):
    id: Optional[int]
    nombre: str
    precio: float
    stock: int
    imagen: Optional[str] = None
    
class ProductoCreateUpdate(BaseModel):
    nombre: str
    precio: float
    stock: int

class CompraRequest(BaseModel):
    nombre_producto: str
    cantidad: int

class PedidoResponse(BaseModel):
    nombre_producto: str
    precio_total: float
    cantidad: int
    fecha_pedido: str
    
class ProductoCarrito(BaseModel):
    nombre: str
    precio: float
    cantidad: int
    
class DeleteResponse(BaseModel):
    mensaje: str

class Venta(BaseModel):
    venta_id: Optional[int]
    pedido_id: int
    cliente_id: int
    nombre_usuario: str
    nombre_producto: str
    cantidad: int
    total_compra: float
    fecha_venta: Optional[str]





usuario_actual = {"tipo_usuario": None, "nombre_usuario": None, "cliente_id": None}










class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Definir rutas que no requieren autenticación
        allowed_paths = ["/login", "/cliente/registrar", "/CargaLogin.html", "/productos"]

        # Permitir acceso público a las rutas permitidas
        if request.url.path not in allowed_paths and not usuario_actual.get("nombre_usuario"):
            return RedirectResponse(url='/CargaLogin.html')
        
        # Llamar al siguiente middleware o al controlador de endpoint
        response = await call_next(request)
        return response

# Agregar el middleware a la aplicación FastAPI
app.add_middleware(AuthMiddleware)



# Endpoint para obtener el rol del usuario
@app.get("/user-role")
def get_user_role():
    if not usuario_actual["nombre_usuario"]:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"role": usuario_actual["tipo_usuario"]}

# Endpoint para la página de usuario
@app.get("/user-page")
def user_page():
    if usuario_actual["tipo_usuario"] != "cliente":
        raise HTTPException(status_code=403, detail="Access forbidden: insufficient permissions")
    return {"message": "Access granted"}

# Endpoint para la página de administrador
@app.get("/admin-page")
def admin_page():
    if usuario_actual["tipo_usuario"] != "administrador":
        raise HTTPException(status_code=403, detail="Access forbidden: insufficient permissions")
    return {"message": "Access granted"}


@app.post("/cliente/registrar")
async def registrar_cliente(cliente: ClienteCreate):
    try:
        # Cifrar la contraseña
        hashed_password = bcrypt.hashpw(cliente.contrasena.encode('utf-8'), bcrypt.gensalt())
        
        query = """
        INSERT INTO Clientes (Nombre, Apellido, CorreoElectronico, NombreUsuario, Contrasena)
        VALUES (?, ?, ?, ?, ?);
        """
        params = (cliente.nombre, cliente.apellido, cliente.correo_electronico, cliente.nombre_usuario, hashed_password.decode('utf-8'))
        ejecutar_consulta(query, params)
        return {"mensaje": "Cliente registrado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login", response_model=LoginResponse)
async def iniciar_sesion(login: LoginRequest, request: Request):
    try:
        # Verificar si el usuario es un cliente
        query_cliente = """
        SELECT ClienteID, Contrasena FROM Clientes WHERE NombreUsuario = ?;
        """
        params_cliente = (login.nombre_usuario,)
        resultado_cliente = ejecutar_consulta(query_cliente, params_cliente)
        
        if resultado_cliente:
            cliente_id, hashed_password = resultado_cliente[0]
            if bcrypt.checkpw(login.contrasena.encode('utf-8'), hashed_password.encode('utf-8')):
                usuario_actual["tipo_usuario"] = "cliente"
                usuario_actual["nombre_usuario"] = login.nombre_usuario
                usuario_actual["cliente_id"] = cliente_id

                # Registrar o actualizar sesión del cliente
                query_sesion = """
                IF EXISTS (SELECT 1 FROM SesionesClientes WHERE ClienteID = ?)
                    UPDATE SesionesClientes SET FechaInicio = GETDATE(), IP = ? WHERE ClienteID = ?
                ELSE
                    INSERT INTO SesionesClientes (ClienteID, FechaInicio, IP) VALUES (?, GETDATE(), ?);
                """
                client_ip = request.client.host
                params_sesion = (usuario_actual["cliente_id"], client_ip, usuario_actual["cliente_id"], usuario_actual["cliente_id"], client_ip)
                ejecutar_consulta(query_sesion, params_sesion)

                return LoginResponse(mensaje="Inicio de sesión exitoso", tipo_usuario="cliente")

        # Verificar si el usuario es un administrador
        query_admin = """
        SELECT AdministradorID, Contrasena FROM Administradores WHERE NombreUsuario = ?;
        """
        params_admin = (login.nombre_usuario,)
        resultado_admin = ejecutar_consulta(query_admin, params_admin)

        if resultado_admin:
            administrador_id, contrasena = resultado_admin[0]
            if login.contrasena == contrasena:
                usuario_actual["tipo_usuario"] = "administrador"
                usuario_actual["nombre_usuario"] = login.nombre_usuario
                usuario_actual["administrador_id"] = administrador_id
                return LoginResponse(mensaje="Inicio de sesión exitoso", tipo_usuario="administrador")

        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
  
    
@app.post("/logout", response_model=LoginResponse)
def cerrar_sesion():
    try:
        # Obtener el ClienteID automáticamente basado en la sesión activa
        cliente_id = usuario_actual.get("cliente_id")

        if cliente_id is not None:
            # Actualizar la tabla SesionesClientes para marcar la sesión como cerrada
            query = """
            UPDATE SesionesClientes
            SET FechaCierre = GETDATE()
            WHERE ClienteID = ? AND FechaCierre IS NULL;
            """
            ejecutar_consulta(query, (cliente_id,))
        
        # Limpiar la información de sesión actual
        usuario_actual["tipo_usuario"] = None
        usuario_actual["nombre_usuario"] = None
        usuario_actual["cliente_id"] = None

        return {"mensaje": "Sesión cerrada exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/sesiones-clientes", response_model=List[dict])
def obtener_sesiones_clientes():
    try:
        query = """
        SELECT sc.SesionID, sc.ClienteID, c.Nombre, c.NombreUsuario, sc.FechaInicio, sc.FechaCierre, sc.IP
        FROM SesionesClientes sc
        JOIN Clientes c ON sc.ClienteID = c.ClienteID;
        """
        sesiones = ejecutar_consulta(query)
        lista_sesiones = [
            {
                "SesionID": sesion[0],
                "ClienteID": sesion[1],
                "NombreCliente": sesion[2],
                "NombreUsuario": sesion[3],
                "FechaCierre": sesion[4],
                "FechaInicio": sesion[5],
                "IP": sesion[6]
            }
            for sesion in sesiones
        ]
        return lista_sesiones
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)











# Configura la carpeta 'imgs' para servir archivos estáticos
app.mount("/imgs", StaticFiles(directory="imgs"), name="imgs")

@app.post("/productos", response_model=Producto)
def crear_producto(
    nombre: str = Form(...), 
    precio: float = Form(...), 
    stock: int = Form(...), 
    imagen: Optional[UploadFile] = File(None)
):
    try:
        
        
        filename = None
        if imagen:
            # Guardar la imagen
            filename = imagen.filename
            filepath = f"imgs/{filename}"
            with open(filepath, "wb") as buffer:
                shutil.copyfileobj(imagen.file, buffer)
        
        query = """
        INSERT INTO Productos (Nombre, Precio, Stock, Imagen)
        VALUES (?, ?, ?, ?);
        """
        params = (nombre, precio, stock, filename)
        ejecutar_consulta(query, params)
        
        query = "SELECT TOP 1 ProductoID, Nombre, Precio, Stock, Imagen FROM Productos ORDER BY ProductoID DESC;"
        producto_creado = ejecutar_consulta(query)[0]
        
        return Producto(
            id=producto_creado[0], 
            nombre=producto_creado[1], 
            precio=producto_creado[2], 
            stock=producto_creado[3], 
            imagen=f"/imgs/{producto_creado[4]}" if producto_creado[4] else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/productos", response_model=List[Producto])
def obtener_productos():
    query = "SELECT ProductoID, Nombre, Precio, Stock, Imagen FROM Productos;"
    productos = ejecutar_consulta(query)
    lista_productos = [
        Producto(
            id=producto[0], 
            nombre=producto[1], 
            precio=producto[2], 
            stock=producto[3], 
            imagen=f"/imgs/{producto[4]}" if producto[4] else None
        )
        for producto in productos
    ]
    return lista_productos
@app.put("/productos/{producto_id}", response_model=Producto)
def actualizar_producto(producto_id: int, producto: ProductoCreateUpdate):
    #if usuario_actual["tipo_usuario"] != "administrador":
     #   raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        query = """
        UPDATE Productos SET Nombre = ?, Precio = ?, Stock = ?
        WHERE ProductoID = ?;
        """
        params = (producto.nombre, producto.precio, producto.stock, producto_id)
        ejecutar_consulta(query, params)
        
        query = "SELECT ProductoID, Nombre, Precio, Stock FROM Productos WHERE ProductoID = ?;"
        producto_actualizado = ejecutar_consulta(query, (producto_id,))[0]
        
        registrar_auditoria("UPDATE", "Productos", producto_id, usuario_actual["nombre_usuario"])
        
        return Producto(id=producto_actualizado[0], nombre=producto_actualizado[1], precio=producto_actualizado[2], stock=producto_actualizado[3])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/productos/{producto_id}")
def eliminar_producto(producto_id: int):
    try:
        # Primero, verificar si el producto existe
        query_verificar_producto = "SELECT ProductoID FROM Productos WHERE ProductoID = ?;"
        params_producto = (producto_id,)
        producto = ejecutar_consulta(query_verificar_producto, params_producto)
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Eliminar el producto de la tabla Productos
        query_eliminar_producto = "DELETE FROM Productos WHERE ProductoID = ?;"
        ejecutar_consulta(query_eliminar_producto, params_producto)
        
        registrar_auditoria("DELETE", "Productos", producto_id, usuario_actual["nombre_usuario"])

        return {"mensaje": "Producto eliminado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/comprar-producto")
def comprar_producto(compra: CompraRequest):
    try:
        # Verificar que el producto existe y obtener su stock y precio
        query_producto = """
        SELECT ProductoID, Nombre, Precio, Stock FROM Productos WHERE Nombre = ?;
        """
        params_producto = (compra.nombre_producto,)
        producto = ejecutar_consulta(query_producto, params_producto)
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        producto_id, nombre_producto, precio, stock_disponible = producto[0]
        
        # Verificar que hay suficiente stock para la compra
        if stock_disponible < compra.cantidad:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        
        # Calcular el total de la compra
        total_compra = precio * compra.cantidad
        
        # Llamar al procedimiento almacenado para registrar el pedido y la venta
        query_registrar_pedido = """
        EXEC RegistrarPedido @ClienteID = ?, @ProductoID = ?, @Cantidad = ?;
        """
        cliente_id = usuario_actual.get("cliente_id")  # Suponiendo que 'usuario_actual' tiene el ID del cliente
        if not cliente_id:
            raise HTTPException(status_code=401, detail="Usuario no autenticado")
        params_registrar_pedido = (cliente_id, producto_id, compra.cantidad)
        ejecutar_consulta(query_registrar_pedido, params_registrar_pedido)
        
        return {"mensaje": "Compra realizada exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/pedido/{pedido_id}", response_model=dict)
def cancelar_pedido(pedido_id: int):
    logging.info(f"Intentando cancelar el pedido: {pedido_id}")

    if usuario_actual["tipo_usuario"] != "cliente":
        logging.error(f"Acceso denegado para el pedido: {pedido_id}")
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    try:
        # Verificar que el pedido pertenece al cliente actual
        query_verificar = """
        SELECT PedidoID, ClienteID, ProductoID, Cantidad FROM Pedidos WHERE PedidoID = ?;
        """
        params_verificar = (pedido_id,)
        logging.debug(f"Ejecutando consulta de verificación: {query_verificar} con params: {params_verificar}")
        resultado = ejecutar_consulta(query_verificar, params_verificar)
        
        if not resultado or resultado[0][1] != usuario_actual["cliente_id"]:
            logging.error(f"Pedido no encontrado o no autorizado para el pedido: {pedido_id}")
            raise HTTPException(status_code=403, detail="Pedido no encontrado o no autorizado")
        
        # Obtener los detalles del pedido
        pedido_id, cliente_id, producto_id, cantidad = resultado[0]
        logging.debug(f"Detalles del pedido obtenidos: PedidoID={pedido_id}, ClienteID={cliente_id}, ProductoID={producto_id}, Cantidad={cantidad}")
        
        # Comenzar una transacción
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            
            try:
                logging.info(f"Insertando en PedidosCancelados: PedidoID={pedido_id}, ClienteID={cliente_id}, ProductoID={producto_id}, Cantidad={cantidad}")
                # Insertar en PedidosCancelados
                query_insertar_cancelado = """
                INSERT INTO PedidosCancelados (PedidoID, ClienteID, ProductoID, Cantidad, FechaCancelacion)
                VALUES (?, ?, ?, ?, GETDATE());
                """
                cursor.execute(query_insertar_cancelado, (pedido_id, cliente_id, producto_id, cantidad))
                
                logging.info(f"Eliminando ventas relacionadas para el pedido: PedidoID={pedido_id}")
                # Eliminar ventas relacionadas con el pedido
                query_eliminar_ventas = """
                DELETE FROM Ventas WHERE PedidoID = ?;
                """
                cursor.execute(query_eliminar_ventas, (pedido_id,))
                
                logging.info(f"Actualizando el stock para el producto: ProductoID={producto_id}, Cantidad={cantidad}")
                # Actualizar el stock
                query_actualizar_stock = """
                UPDATE Productos
                SET Stock = Stock + ?
                WHERE ProductoID = ?;
                """
                cursor.execute(query_actualizar_stock, (cantidad, producto_id))
                
                logging.info(f"Eliminando de la tabla Pedidos: PedidoID={pedido_id}")
                # Eliminar el pedido de la tabla Pedidos
                query_eliminar_pedido = """
                DELETE FROM Pedidos WHERE PedidoID = ?;
                """
                cursor.execute(query_eliminar_pedido, (pedido_id,))
                
                # Confirmar la transacción
                conn.commit()
                logging.info("Transacción confirmada")
                
                return {"mensaje": "Pedido cancelado exitosamente"}
            except Exception as e:
                logging.error(f"Error en la transacción, revirtiendo cambios para el pedido: {pedido_id}, error: {e}")
                # Revertir la transacción en caso de error
                conn.rollback()
                raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logging.error(f"Error al procesar la cancelación del pedido: {pedido_id}, error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@app.get("/mis-pedidos", response_model=List[dict])
def obtener_mis_pedidos():
    try:
        cliente_id = usuario_actual["cliente_id"]  # Suponiendo que 'usuario_actual' tiene el ID del cliente

        # Consulta para obtener los detalles de los pedidos del cliente
        query_pedidos = """
        SELECT p.PedidoID, p.Cantidad, p.FechaCompra, pr.Nombre, pr.Precio * p.Cantidad AS PrecioTotal
        FROM Pedidos p
        JOIN Productos pr ON p.ProductoID = pr.ProductoID
        WHERE p.ClienteID = ?;
        """
        params_pedidos = (cliente_id,)
        pedidos = ejecutar_consulta(query_pedidos, params_pedidos)
        
        lista_pedidos = [
            {
                "pedido_id": pedido[0],
                "nombre_producto": pedido[3],
                "precio_total": float(pedido[4]),  # Asegurarse de que precio_total sea un float
                "cantidad": pedido[1],
                "fecha_pedido": pedido[2].strftime('%Y-%m-%d %H:%M:%S')
            }
            for pedido in pedidos
        ]
        return lista_pedidos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/pedidos", response_model=List[dict])
def obtener_todos_los_pedidos():
    try:
        # Consulta para obtener los detalles de todos los pedidos
        query_pedidos = """
        SELECT p.PedidoID, c.Nombre AS ClienteNombre, pr.Nombre AS ProductoNombre, p.Cantidad, p.FechaCompra
        FROM Pedidos p
        JOIN Clientes c ON p.ClienteID = c.ClienteID
        JOIN Productos pr ON p.ProductoID = pr.ProductoID;
        """
        pedidos = ejecutar_consulta(query_pedidos)
        
        lista_pedidos = [
            {
                "pedido_id": pedido[0],
                "cliente_nombre": pedido[1],
                "producto_nombre": pedido[2],
                "cantidad": pedido[3],
                "fecha_compra": pedido[4].strftime('%Y-%m-%d %H:%M:%S')
            }
            for pedido in pedidos
        ]
        return lista_pedidos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



import logging

logging.basicConfig(level=logging.INFO)

@app.delete("/productos/{producto_id}")
def eliminar_producto(producto_id: int):
    #if usuario_actual["tipo_usuario"] != "administrador":
    #   raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        # Actualizar registros en Pedidos para establecer ProductoID a NULL
        query_actualizar_pedidos = "UPDATE Pedidos SET ProductoID = NULL WHERE ProductoID = ?"
        params_pedidos = (producto_id,)
        ejecutar_consulta(query_actualizar_pedidos, params_pedidos)
        
        # Actualizar registros en PedidosCancelados para establecer ProductoID a NULL
        query_actualizar_pedidos_cancelados = "UPDATE PedidosCancelados SET ProductoID = NULL WHERE ProductoID = ?"
        params_pedidos_cancelados = (producto_id,)
        ejecutar_consulta(query_actualizar_pedidos_cancelados, params_pedidos_cancelados)
        
        # Finalmente, eliminar el producto
        query_eliminar_producto = "DELETE FROM Productos WHERE ProductoID = ?;"
        params_producto = (producto_id,)
        ejecutar_consulta(query_eliminar_producto, params_producto)
        
        registrar_auditoria("DELETE", "Productos", producto_id, usuario_actual["nombre_usuario"])
        
        return {"mensaje": "Producto eliminado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)

@app.get("/ganancia-total", response_model=dict)
def obtener_ganancia_total():
    if usuario_actual["tipo_usuario"] != "administrador":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    try:
        query = """
        SELECT SUM(TotalCompra) AS GananciaTotal
        FROM Ventas;
        """
        resultado = ejecutar_consulta(query)
        ganancia_total = resultado[0][0] if resultado and resultado[0][0] else 0
        return {"GananciaTotal": ganancia_total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/productos-mas-solicitados", response_model=List[dict])
def obtener_productos_mas_solicitados():
    #if usuario_actual["tipo_usuario"] != "administrador":
     #   raise HTTPException(status_code=403, detail="Acceso denegado")

    try:
        query = """
        SELECT NombreProducto, SUM(Cantidad) AS TotalVendido
        FROM Ventas
        GROUP BY NombreProducto
        ORDER BY TotalVendido DESC;
        """
        productos = ejecutar_consulta(query)
        lista_productos = [
            {
                "NombreProducto": producto[0],
                "TotalVendido": producto[1]
            }
            for producto in productos
        ]
        return lista_productos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/verificar-stock", response_model=List[dict])
def verificar_stock_productos():
    #if usuario_actual["tipo_usuario"] != "administrador":
     #   raise HTTPException(status_code=403, detail="Acceso denegado")
    
    try:
        query = """
        SELECT ProductoID, Nombre, Stock
        FROM Productos;
        """
        productos = ejecutar_consulta(query)
        lista_productos = [
            {
                "ProductoID": producto[0],
                "Nombre": producto[1],
                "Stock": producto[2],
                "Mensaje": "Favor de actualizar inventario" if producto[2] < 10 else ""
            }
            for producto in productos
        ]
        return lista_productos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ventas", response_model=List[Venta])
def obtener_ventas():
    try:
        query = """
        SELECT VentaID, PedidoID, ClienteID, NombreUsuario, NombreProducto, Cantidad, TotalCompra, FechaVenta
        FROM Ventas;
        """
        ventas = ejecutar_consulta(query)
        
        lista_ventas = [
            Venta(
                venta_id=venta[0],
                pedido_id=venta[1],
                cliente_id=venta[2],
                nombre_usuario=venta[3],
                nombre_producto=venta[4],
                cantidad=venta[5],
                total_compra=venta[6],
                fecha_venta=venta[7].strftime('%Y-%m-%d %H:%M:%S')
            )
            for venta in ventas
        ]
        return lista_ventas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    
    
    
    
class DatosPanel(BaseModel):
    productos: int
    stock: int
    clientes: int
    pedidos: int

class DatosGraficas(BaseModel):
    barras: List[int]
    categoriasBarras: List[str]
    pastel: List[int]
    categoriasPastel: List[str]

# Mapeo de los números de los meses a nombres en español
meses_espanol = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

@app.get("/datos-panel", response_model=DatosPanel)
def get_datos_panel():
    try:
        query_productos = "SELECT COUNT(*) FROM Productos;"
        query_stock = "SELECT SUM(Stock) FROM Productos;"
        query_clientes = "SELECT COUNT(*) FROM Clientes;"
        query_pedidos = "SELECT COUNT(*) FROM Pedidos;"

        productos = ejecutar_consulta(query_productos)[0][0]
        stock = ejecutar_consulta(query_stock)[0][0]
        clientes = ejecutar_consulta(query_clientes)[0][0]
        pedidos = ejecutar_consulta(query_pedidos)[0][0]

        return DatosPanel(productos=productos, stock=stock, clientes=clientes, pedidos=pedidos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/datos-graficas", response_model=DatosGraficas)
def get_datos_graficas():
    try:
        query_barras = """
        SELECT MONTH(FechaCompra) AS Mes, COUNT(*) AS Total
        FROM Pedidos
        GROUP BY MONTH(FechaCompra)
        ORDER BY MONTH(FechaCompra);
        """
        query_pastel = """
        SELECT Nombre, COUNT(*) AS Total
        FROM Productos
        JOIN Pedidos ON Productos.ProductoID = Pedidos.ProductoID
        GROUP BY Nombre;
        """

        barras = ejecutar_consulta(query_barras)
        pastel = ejecutar_consulta(query_pastel)

        categorias_barras = [meses_espanol[row[0]] for row in barras]
        data_barras = [row[1] for row in barras]

        categorias_pastel = [row[0] for row in pastel]
        data_pastel = [row[1] for row in pastel]

        return DatosGraficas(barras=data_barras, categoriasBarras=categorias_barras, pastel=data_pastel, categoriasPastel=categorias_pastel)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))