-- Crear la base de datos y usarla
CREATE DATABASE TiendaOnline;
GO
USE TiendaOnline;
GO

-- Tabla Clientes
CREATE TABLE Clientes (
    ClienteID INT PRIMARY KEY IDENTITY(1,1),
    Nombre NVARCHAR(100) NOT NULL,
    Apellido NVARCHAR(100) NOT NULL,
    CorreoElectronico NVARCHAR(100) NOT NULL UNIQUE,
    NombreUsuario NVARCHAR(50) NOT NULL UNIQUE,
    Contrasena NVARCHAR(255) NOT NULL
);

-- Tabla SesionesClientes
CREATE TABLE SesionesClientes (
    SesionID INT PRIMARY KEY IDENTITY(1,1),
    ClienteID INT NOT NULL,
    FechaInicio DATETIME DEFAULT GETDATE(),
    FechaCierre DATETIME NULL, -- A�adido para registrar el cierre de sesi�n
    IP NVARCHAR(50),
    FOREIGN KEY (ClienteID) REFERENCES Clientes(ClienteID)
);

-- Tabla Administradores
CREATE TABLE Administradores (
    AdministradorID INT PRIMARY KEY IDENTITY(1,1),
    NombreUsuario NVARCHAR(50) NOT NULL UNIQUE,
    Contrasena NVARCHAR(255) NOT NULL
);

-- Insertar un administrador con contrase�a en texto plano
INSERT INTO Administradores (NombreUsuario, Contrasena)
VALUES ('admin', 'admin');

-- Tabla Productos
CREATE TABLE Productos (
    ProductoID INT PRIMARY KEY IDENTITY(1,1),
    Nombre NVARCHAR(100) NOT NULL,
    Precio DECIMAL(10, 2) NOT NULL,
    Stock INT NOT NULL,
    Imagen NVARCHAR(255) -- Columna para almacenar la ruta de la imagen
);

-- Tabla AuditoriaCRUD
CREATE TABLE AuditoriaCRUD (
    AuditoriaID INT PRIMARY KEY IDENTITY(1,1),
    TipoOperacion NVARCHAR(10) NOT NULL,  -- CREATE, READ, UPDATE, DELETE
    Tabla NVARCHAR(50) NOT NULL,
    RegistroID INT NOT NULL,
    Usuario NVARCHAR(50) NOT NULL,
    Fecha DATETIME DEFAULT GETDATE()
);

-- Tabla Pedidos
CREATE TABLE Pedidos (
    PedidoID INT PRIMARY KEY IDENTITY(1,1),
    ClienteID INT NOT NULL,
    ProductoID INT NULL,
    Cantidad INT NOT NULL,
    FechaCompra DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (ClienteID) REFERENCES Clientes(ClienteID),
    FOREIGN KEY (ProductoID) REFERENCES Productos(ProductoID)
    ON DELETE SET NULL
);

-- Tabla PedidosCancelados sin clave for�nea en PedidoID
CREATE TABLE PedidosCancelados (
    PedidoCanceladoID INT PRIMARY KEY IDENTITY(1,1),
    PedidoID INT NOT NULL,
    ClienteID INT NOT NULL,
    ProductoID INT NULL,
    Cantidad INT NOT NULL,
    FechaCancelacion DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (ClienteID) REFERENCES Clientes(ClienteID),
    FOREIGN KEY (ProductoID) REFERENCES Productos(ProductoID)
    ON DELETE SET NULL
);

-- Tabla Ventas
CREATE TABLE Ventas (
    VentaID INT PRIMARY KEY IDENTITY(1,1),
    PedidoID INT NOT NULL,
    ClienteID INT NOT NULL,
    NombreUsuario NVARCHAR(50) NOT NULL,
    NombreProducto NVARCHAR(100) NOT NULL,
    Cantidad INT NOT NULL,
    TotalCompra DECIMAL(10, 2) NOT NULL,
    FechaVenta DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (ClienteID) REFERENCES Clientes(ClienteID),
    FOREIGN KEY (PedidoID) REFERENCES Pedidos(PedidoID)
);

-- �ndices
CREATE INDEX idx_Productos_nombres ON Productos(Nombre);
CREATE INDEX idx_Cliente_email ON Clientes(CorreoElectronico);
CREATE INDEX idx_Pedidos_fechaPedido ON Pedidos(FechaCompra);
GO

-- Procedimiento Almacenado para Registrar Pedido
DROP PROCEDURE IF EXISTS RegistrarPedido;
GO
CREATE PROCEDURE RegistrarPedido
    @ClienteID INT,
    @ProductoID INT,
    @Cantidad INT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        
        DECLARE @StockActual INT;
        SELECT @StockActual = Stock FROM Productos WHERE ProductoID = @ProductoID;
        
        IF @StockActual < @Cantidad
        BEGIN
            THROW 50001, 'Stock insuficiente para realizar el pedido.', 1;
        END

        -- Insertar el pedido
        INSERT INTO Pedidos (ClienteID, ProductoID, Cantidad, FechaCompra)
        VALUES (@ClienteID, @ProductoID, @Cantidad, GETDATE());

        -- Obtener el ID del nuevo pedido
        DECLARE @NuevoPedidoID INT;
        SELECT @NuevoPedidoID = SCOPE_IDENTITY();

        -- Actualizar el stock
        UPDATE Productos
        SET Stock = Stock - @Cantidad
        WHERE ProductoID = @ProductoID;

        -- Obtener detalles del cliente y producto
        DECLARE @NombreUsuario NVARCHAR(50);
        DECLARE @NombreProducto NVARCHAR(100);
        DECLARE @Precio DECIMAL(10, 2);
        DECLARE @TotalCompra DECIMAL(10, 2);

        SELECT @NombreUsuario = NombreUsuario FROM Clientes WHERE ClienteID = @ClienteID;
        SELECT @NombreProducto = Nombre, @Precio = Precio FROM Productos WHERE ProductoID = @ProductoID;
        SET @TotalCompra = @Cantidad * @Precio;

        -- Insertar la venta
        INSERT INTO Ventas (ClienteID, NombreUsuario, NombreProducto, Cantidad, TotalCompra, FechaVenta, PedidoID)
        VALUES (@ClienteID, @NombreUsuario, @NombreProducto, @Cantidad, @TotalCompra, GETDATE(), @NuevoPedidoID);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END
GO

-- Procedimiento Almacenado para Cancelar Pedido
DROP PROCEDURE IF EXISTS CancelarPedido;
GO
CREATE PROCEDURE CancelarPedido
    @PedidoID INT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        -- Mover el pedido a la tabla PedidosCancelados
        INSERT INTO PedidosCancelados (PedidoID, ClienteID, ProductoID, Cantidad, FechaCancelacion)
        SELECT PedidoID, ClienteID, ProductoID, Cantidad, GETDATE()
        FROM Pedidos
        WHERE PedidoID = @PedidoID;

        -- Eliminar las ventas relacionadas con el pedido
        DELETE FROM Ventas
        WHERE PedidoID = @PedidoID;

        -- Eliminar el pedido de la tabla Pedidos
        DELETE FROM Pedidos
        WHERE PedidoID = @PedidoID;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END
GO

-- Trigger para Auditoria de Productos
CREATE TRIGGER DisparadorAuditoriaProductos
ON Productos
AFTER INSERT, UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Operacion NVARCHAR(10);
    DECLARE @RegistroID INT;
    DECLARE @Usuario NVARCHAR(50);

    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted)
    BEGIN
        SET @Operacion = 'UPDATE';
        SELECT @RegistroID = ProductoID FROM inserted;
    END
    ELSE IF EXISTS (SELECT * FROM inserted)
    BEGIN
        SET @Operacion = 'INSERT';
        SELECT @RegistroID = ProductoID FROM inserted;
    END
    ELSE IF EXISTS (SELECT * FROM deleted)
    BEGIN
        SET @Operacion = 'DELETE';
        SELECT @RegistroID = ProductoID FROM deleted;
    END

    SET @Usuario = SYSTEM_USER; -- Esto asume que el nombre de usuario es el usuario del sistema ejecutando la operaci�n
    INSERT INTO AuditoriaCRUD (TipoOperacion, Tabla, RegistroID, Usuario, Fecha)
    VALUES (@Operacion, 'Productos', @RegistroID, @Usuario, GETDATE());
END
GO

-- Consultas para Ver Datos
SELECT * FROM Clientes;
SELECT * FROM Productos;
SELECT * FROM AuditoriaCRUD;
SELECT * FROM SesionesClientes;
SELECT * FROM Pedidos;
SELECT * FROM Ventas;
SELECT * FROM PedidosCancelados;

