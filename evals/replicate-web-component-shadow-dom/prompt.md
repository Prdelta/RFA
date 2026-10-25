---
tags: [reverse-engineer-frontend]
max_turns: 45
timeout_seconds: 1000
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

https://ejemplo-design-system.com usa web components (shadow DOM) y colores oklch, parece Tailwind v4 con container queries. Replica la home en React + Tailwind y dame los tokens, incluidos los colores reales (no me valen 'transparent' ni que te saltes lo que hay dentro de los componentes).
