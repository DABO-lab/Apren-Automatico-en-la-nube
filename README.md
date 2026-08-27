<div style="font-family: Arial;">
<img src="https://udemedellin.edu.co/wp-content/uploads/2022/10/logo_udemedellin2.png" width="30%">
<h3 style="text-align: center;">
<b>ESPECIALIZACIÓN EN CIENCIA DE DATOS E INGELIGENCIA ARTIFICIAL</b>
</h3>
<h3 style="text-align: center; color:  #C2262B;"> <!--Color institucional-->
<strong>Aprendizaje de MLOps<strong>
</h3>
<h3>
<b>Tema:</b> Proyecto inicial para Ciencia de Datos
</h3>
<hr style="width:100%; border:1px solid withe;">
<h6 style="text-align: rigth; margin-bottom: 5px">
<b>INTEGRANTES:</b> Bueno Osorno Dubian Andres
- Ceballos Bedoya Catherine - Rivera Guzman Yesenia - Salazar Seguro Maria Jimena
 <br><b>FECHA:</b> 08-2026<br>
</h6>
</div>

---
## ¿De qué se trata nuestro proyecto?

Decidimos trabajar con datos de Citibike (un sistema de transporte de bicicletas compartidas). La idea principal es resolver un problema muy común en logística urbana: **predecir cuánto tiempo va a durar el viaje de un usuario**.

## Los datos que vamos a usar

Estamos utilizando el dataset **JC-202607-citibike-tripdata.csv** que corresponde a los viajes de julio de 2026. Este archivo tiene un poco más de 100 mil registros y nos entrega información clave como:

* La fecha y hora exacta en la que empieza y termina cada viaje
* Las estaciones de origen y destino con sus respectivas coordenadas
* El tipo de bicicleta (por ejemplo si es eléctrica)
* Si la persona que alquila es miembro suscrito o un usuario casual

> **Nota:** El archivo CSV original no está subido directamente a este repositorio para no saturar el peso y mantener las buenas prácticas de Git.

## Nuestro verdadero reto

Más allá de lograr un modelo matemático con una precisión perfecta, lo que queremos en este proyecto es poner a prueba el ciclo de vida completo de machine learning. Básicamente vamos a construir un pipeline que incluya:

* **Experimentación:** Entrenar el modelo y guardar los resultados con herramientas de tracking
* **Orquestación:** Automatizar la limpieza de datos y el entrenamiento
* **Despliegue:** Poner el modelo a funcionar (posiblemente a través de una API local)
* **Monitoreo:** Estar pendientes de que el modelo no pierda rendimiento cuando lleguen datos nuevos

## Lo que sigue

Por ahora tenemos lista esta estructura básica del repositorio y el conjunto de datos seleccionado. En los próximos días empezaremos a subir los primeros notebooks con la exploración de los datos y los scripts de entrenamiento iniciales.
