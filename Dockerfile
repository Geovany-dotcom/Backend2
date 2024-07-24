# Usa una imagen base oficial de Python
FROM python:3.11

# Establece el directorio de trabajo
WORKDIR /app

# Copia los archivos de requisitos y el script de inicio a la imagen
COPY requirements.txt .
COPY start.sh .

# Actualiza los paquetes del sistema e instala las dependencias necesarias
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    unixodbc-dev \
    gnupg \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Instala las dependencias de Python
RUN pip install -r requirements.txt

# Copia el resto del código de la aplicación
COPY . .

# Establece permisos ejecutables para el script de inicio
RUN chmod +x start.sh

# Comando para ejecutar el script de inicio
CMD ["./start.sh"]
