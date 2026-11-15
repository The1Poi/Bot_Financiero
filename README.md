# Chatbot Financiero basado en un Autómata Finito Determinista (AFD)

Este repositorio contiene el desarrollo de un prototipo funcional de chatbot financiero para **Telegram**, diseñado para agilizar el registro secuencial de gastos personales eliminando la fricción de los formularios tradicionales mediante una interfaz conversacional de flujo estricto.

El núcleo de la solución se fundamenta en la **Teoría de la Computación**, implementando un **Autómata Finito Determinista** $M = (Q, \Sigma, \delta, q_0, F)$ que gobierna el diálogo a través de tres estados explícitos: *Inactivo* ($S_0$), *Esperando Monto* ($S_1$) y *Esperando Concepto* ($S_2$). Este modelo matemático garantiza que cada etapa admita únicamente entradas sintáctica y semánticamente válidas, rechazando entradas fuera de secuencia sin corromper el estado actual ni los datos temporales.

## Características técnicas principales

* **Arquitectura modular en Python 3:** Separación estricta entre la interfaz de mensajería (*HTTPS Long Polling* con Telegram Bot API), el motor formal del AFD, el validador de entradas, el módulo de consulta en reposo (`/informacion`) y la capa de persistencia.
* **Precisión monetaria e integridad en SQLite:** Almacenamiento local mediante consultas SQL parametrizadas y conversión exacta de montos decimales a unidades enteras menores (centavos como `INTEGER`), evitando errores de punto flotante (`IEEE 754`) y confirmando transacciones únicamente tras escrituras exitosas.

## Autores

* **Carlos S. Antolinez**
* **Sebastián A. Basto**
* **Jeison S. Clavijo**
* **Johan C. Bonett**

*Programa de Ingeniería de Sistemas — Asignatura: Teoría de la Computación — Universidad de Pamplona (2026).*
