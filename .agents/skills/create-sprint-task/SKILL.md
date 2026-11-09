---
name: create-sprint-task
description: "Skill de decomposição de tarefas para geração padronizada de User Stories e Tasks de Sprint."
---

# Skill: create-sprint-task

Utilize este modelo e critérios sempre que for solicitado a criar ou estruturar tarefas de backlog.

## Critérios de Qualidade (INVEST)
- Mantenha histórias autossuficientes e com estimativas plausíveis.
- Descreva critérios de aceitação objetivos no formato Gherkin.

## Template de Saída

```markdown
### [US-XXX] Título Conciso

**Como** [persona/usuário]  
**Eu quero** [funcionalidade ou ação]  
**Para que** [resultado ou agregação de valor]  

---

#### 📋 Descrição e Regras de Negócio
<Contexto funcional, limites de implementação e requisitos mínimos>

#### ✅ Critérios de Aceite
- **Cenário 1: [Caminho Feliz]**
  - **Dado** <condição prévia do sistema>
  - **Quando** <o usuário realiza a ação>
  - **Então** <o comportamento esperado é validado>

- **Cenário 2: [Tratamento de Falha]**
  - **Dado** <dados incorretos ou indisponibilidade>
  - **Quando** <a chamada é disparada>
  - **Então** <uma resposta de erro apropriada é devolvida>

#### 🛠️ Checklist de Execução
- [ ] Implementação de lógica/rotas
- [ ] Testes unitários/integração
- [ ] Validação de segurança

#### 🏷️ Metadados
- **Prioridade:** [Alta | Média | Baixa]
- **Estimativa:** [Story Points / Tamanho P-M-G]
```
