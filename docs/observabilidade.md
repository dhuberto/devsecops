### Documentando pelo menos três consultas LogQL testadas pela equipe, incluindo, obrigatoriamente, a query para contagem de falhas de login por IP.
<img width="1618" height="814" alt="{E38E64D3-C32F-4E2D-B0FE-825EAD7054F3}" src="https://github.com/user-attachments/assets/ba34868e-d9c8-4c1f-931e-b974ffa1278c" />

### Query
```bash
{job="taskflow"} | json | event = "login_attempt" | result = "failure" | username = "admin"
```

