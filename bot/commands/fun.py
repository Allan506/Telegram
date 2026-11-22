"""Comandos de entretenimiento. Todo local: no dependen de servicios externos."""

from __future__ import annotations

import random

from .registry import command

CHISTES = [
    "¿Qué le dice un bit al otro? Nos vemos en el bus.",
    "Hay dos tipos de personas: las que entienden la recursividad y las que entienden la recursividad.",
    "¿Por qué los programadores prefieren el modo oscuro? Porque la luz atrae a los bugs.",
    "Un programador fue al médico: «Doctor, me duele aquí». El médico: «Pues no toques ahí».",
    "¿Cuántos programadores hacen falta para cambiar una bombilla? Ninguno, es un problema de hardware.",
    "Mi código no tiene errores, tiene características no documentadas.",
    "¿Qué es un algoritmo? Una receta, pero con más café.",
    "Existen 10 tipos de personas: las que entienden binario y las que no.",
]

FRASES = [
    "El mejor momento para plantar un árbol fue hace 20 años. El segundo mejor momento es ahora.",
    "La simplicidad es la máxima sofisticación.",
    "No cuentes los días, haz que los días cuenten.",
    "Lo que no se mide, no se mejora.",
    "Primero haz que funcione, luego haz que sea correcto, después haz que sea rápido.",
    "Un barco en el puerto está seguro, pero no es para eso para lo que se construyen los barcos.",
    "La disciplina es el puente entre las metas y los logros.",
]

DADOS = ("⚀", "⚁", "⚂", "⚃", "⚄", "⚅")


@command("dado", "Lanza un dado", "/dado [caras]")
def dado(ctx):
    caras = 6
    if ctx.args:
        try:
            caras = int(ctx.args[0])
        except ValueError:
            return "El número de caras debe ser un entero. Ejemplo: <code>/dado 20</code>"
        if not 2 <= caras <= 1000:
            return "Elige entre 2 y 1000 caras. Ejemplo: <code>/dado 20</code>"

    valor = random.randint(1, caras)
    if caras == 6:
        return f"{DADOS[valor - 1]} Has sacado un <b>{valor}</b>"
    return f"🎲 Has sacado un <b>{valor}</b> (de {caras})"


@command("moneda", "Lanza una moneda al aire")
def moneda(ctx):
    resultado = random.choice(("cara", "cruz"))
    icono = "🪙" if resultado == "cara" else "🔁"
    return f"{icono} Ha salido <b>{resultado}</b>"


@command("chiste", "Cuenta un chiste de programadores")
def chiste(ctx):
    return f"😄 {random.choice(CHISTES)}"


@command("frase", "Comparte una frase motivacional")
def frase(ctx):
    return f"💡 {random.choice(FRASES)}"
