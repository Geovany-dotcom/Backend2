# Usa una imagen base de Python
FROM python:3.11-slim

# Instala las dependencias necesarias
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    unixodbc-dev

# Agrega la clave y repositorio para el controlador ODBC de Microsoft
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list

# Instala el controlador ODBC de Microsoft
RUN apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Instala las dependencias de Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copia el resto del código de tu aplicación
COPY . .

# Comando para iniciar tu aplicación
CMD ["./start.sh"]
