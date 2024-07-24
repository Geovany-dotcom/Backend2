FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y curl gnupg apt-transport-https unixodbc-dev

# Añadir claves y repositorios de Microsoft
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/debian/10/prod.list | tee /etc/apt/sources.list.d/mssql-release.list

# Instalar el controlador ODBC de Microsoft para SQL Server
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Crear directorio de la aplicación
WORKDIR /app

# Copiar archivos de la aplicación
COPY . .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Hacer ejecutable el script de inicio
RUN chmod +x start.sh

# Comando para iniciar la aplicación
CMD ["./start.sh"]
