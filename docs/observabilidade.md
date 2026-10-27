### Documentando pelo menos três consultas LogQL testadas pela equipe, incluindo, obrigatoriamente, a query para contagem de falhas de login por IP.
<img width="1618" height="814" alt="{E38E64D3-C32F-4E2D-B0FE-825EAD7054F3}" src="https://github.com/user-attachments/assets/ba34868e-d9c8-4c1f-931e-b974ffa1278c" />

### Query
```bash
{job="taskflow"} | json | event = "login_attempt" | result = "failure" | username = "admin"
```

# Arquitetura e Coleta de Logs - Stack Grafana/Loki/Promtail

## 1. Fluxo de Coleta de Logs
1. **Aplicação (TaskFlow):** Emite eventos de segurança e requisições formatadas em linhas JSON planas no arquivo `logs/taskflow.log`.
2. **Promtail (Agente):** Monitora o volume montado em `/var/log/taskflow/*.log`, extrai os rótulos (`level`, `event`, `result`) do JSON e envia os dados via API HTTP para o servidor Loki.
3. **Loki (Datastore):** Armazena e indexa os logs com base nos rótulos recebidos.
4. **Grafana (Visualização):** Conecta-se ao Loki como Datasource e executa queries LogQL para dashboards e alertas.

---

## 2. Consultas LogQL Testadas

### Consulta 1: Agrupamento e contagem de falhas de login por IP de origem (OBRIGATÓRIA)
```logql
sum by (ip) (count_over_time({job="taskflow"} | json | event="login_attempt" | result="failure" [5m]))
