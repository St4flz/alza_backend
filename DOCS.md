# DOCS.md — FinanzasAPI Endpoints

## Overview

**Backend:** FinanzasAPI  
**Framework:** FastAPI + SQLAlchemy + Supabase  
**API Prefix:** `/api/v1`  
**Auth:** JWT Bearer token via `Authorization: Bearer <token>` (Supabase)  
**CORS:** All origins allowed  
**Docs interactivas:** `GET /docs` (Swagger) | `GET /redoc` (ReDoc)  
**Formato de respuesta estándar:**

```json
{ "success": true, "message": "OK", "data": { ... } }
```

---

## 🔐 Autenticación

Todos los endpoints privados requieren el encabezado:

```
Authorization: Bearer <token_jwt_supabase>
```

El token es decodificado por el servidor; el `sub` del payload se usa como `user_id`.  
No es necesario enviar `user_id` en el cuerpo o query; se obtiene del token automáticamente.

---

## Wallets

> **Ruta base:** `/api/v1/wallets`

### `GET /api/v1/wallets`

Lista todas las wallets del usuario autenticado.

**Request:**  
- Encabezado: `Authorization: Bearer <token>`
- Sin parámetros adicionales.

**Response 200:**
```json
{
  "success": true,
  "message": "OK",
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "name": "Efectivo",
      "balance": 1500.0,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

---

### `GET /api/v1/wallets/{wallet_id}`

Obtiene una wallet específica por su ID.

**Request:**
```
GET /api/v1/wallets/{wallet_id}
Authorization: Bearer <token>
```

**Response 200:**
```json
{ "success": true, "message": "OK", "data": { /* Wallet schema */ } }
```

**Errores:** `404` si no existe o no pertenece al usuario.

---

### `POST /api/v1/wallets`

Crea una nueva wallet. El `user_id` se asigna automáticamente desde el token.

**Request:**
```json
{
  "data": {
    "name": "Efectivo",
    "balance": 0.0
  }
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `name` | `string` | ✅ | Nombre de la wallet |
| `balance` | `float` | ❌ | Saldo inicial (por defecto `0.0`) |

**Response 201:**
```json
{ "success": true, "message": "Creado exitosamente", "data": { /* Wallet schema con id generado */ } }
```

---

### `PATCH /api/v1/wallets/{wallet_id}`

Actualiza una wallet existente. Solo se modifican los campos enviados.

**Request:**
```json
{
  "data": {
    "name": "Efectivo",
    "balance": 2000.0
  }
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `name` | `string` | ❌ | Nuevo nombre |
| `balance` | `float` | ❌ | Nuevo saldo |

**Response 200:**
```json
{ "success": true, "message": "OK", "data": { /* Wallet actualizada */ } }
```

---

### `DELETE /api/v1/wallets/{wallet_id}`

Elimina una wallet.

**Request:**
```
DELETE /api/v1/wallets/{wallet_id}
Authorization: Bearer <token>
```

**Response 200:**
```json
{ "success": true, "message": "Eliminado exitosamente", "data": null }
```

**Errores:** `404` si no existe. `403` si no pertenece al usuario.

---

## Transactions

> **Ruta base:** `/api/v1/transactions`

> **Importante:** Al crear, actualizar o eliminar una transacción, el saldo de la `wallet` asociada se ajusta automáticamente (`+amount` para `income`, `−amount` para `expense`).

---

### `GET /api/v1/transactions`

Lista transacciones del usuario con filtros opcionales y paginación.

**Request:**
```
GET /api/v1/transactions?wallet_id=uuid&category_id=uuid&type=income&start_date=2024-01-01&end_date=2024-01-31&page=1&limit=20
Authorization: Bearer <token>
```

| Query param | Tipo | Requerido | Descripción |
|-------------|------|-----------|-------------|
| `wallet_id` | `uuid` | ❌ | Filtrar por wallet |
| `category_id` | `uuid` | ❌ | Filtrar por categoría |
| `type` | `"income" \| "expense"` | ❌ | Filtrar por tipo |
| `start_date` | `string` (ISO 8601) | ❌ | Fecha de inicio |
| `end_date` | `string` (ISO 8601) | ❌ | Fecha de fin |
| `page` | `int` | ❌ | Número de página (por defecto `1`) |
| `limit` | `int` | ❌ | Registros por página (por defecto `20`) |

**Response 200:**
```json
{
  "success": true,
  "message": "OK",
  "data": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "title": "Sueldo",
      "description": "Sueldo mensual",
      "amount": 5000.0,
      "type": "income",
      "wallet_id": "uuid",
      "category_id": "uuid",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-01T00:00:00"
    }
  ]
}
```

> **Nota:** La respuesta no incluye `tag_ids` en el listado. Para obtener los tags de una transacción, consultar el endpoint individual.

---

### `GET /api/v1/transactions/{transaction_id}`

Obtiene una transacción específica.

**Response 200:** objeto `TransactionResponseSerializer` (igual que el de listado).

---

### `POST /api/v1/transactions`

Crea una nueva transacción. Ajusta automáticamente el saldo de la wallet asociada.

**Request:**
```json
{
  "data": {
    "title": "Sueldo",
    "description": "Sueldo mensual enero",
    "amount": 5000.0,
    "type": "income",
    "wallet_id": "uuid-de-la-wallet",
    "category_id": "uuid-de-la-categoria",
    "tag_ids": ["uuid-tag-1", "uuid-tag-2"]
  }
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `title` | `string` | ✅ | Título de la transacción |
| `description` | `string` | ❌ | Descripción |
| `amount` | `float` | ✅ | Monto; debe ser **mayor a 0** |
| `type` | `string` | ✅ | `"income"` o `"expense"` |
| `wallet_id` | `uuid` | ✅ | ID de la wallet vinculada |
| `category_id` | `uuid` | ✅ | ID de la categoría vinculada |
| `tag_ids` | `uuid[]` | ❌ | Lista de IDs de tags (por defecto `[]`) |

**Response 201:**
```json
{ "success": true, "message": "Creado exitosamente", "data": { /* Transaction schema */ } }
```

**Errores:** `422` si `amount <= 0` o `type` no es `"income"`/`"expense"`.

---

### `PATCH /api/v1/transactions/{transaction_id}`

Actualiza una transacción. Reajusta el saldo de la wallet asociada.

**Request:** Igual que `POST`, los campos son todos opcionales (solo se actualizan los enviados).

**Response 200:**
```json
{ "success": true, "message": "OK", "data": { /* Transaction actualizada */ } }
```

---

### `DELETE /api/v1/transactions/{transaction_id}`

Elimina una transacción. Revierte el ajuste del saldo de la wallet automáticamente.

**Request:**
```
DELETE /api/v1/transactions/{transaction_id}
Authorization: Bearer <token>
```

**Response 200:**
```json
{ "success": true, "message": "Eliminado exitosamente", "data": null }
```

---

## Categories

> **Ruta base:** `/api/v1/categories`

### `GET /api/v1/categories`

Lista todas las categorías del usuario autenticado.

**Request:**  
- Encabezado: `Authorization: Bearer <token>`

**Response 200:**
```json
{
  "success": true,
  "message": "OK",
  "data": [
    { "id": "uuid", "user_id": "uuid", "name": "Comida", "created_at": "...", "updated_at": "..." }
  ]
}
```

---

### `GET /api/v1/categories/{category_id}`

Obtiene una categoría específica.

---

### `POST /api/v1/categories`

Crea una nueva categoría. El `user_id` se asigna desde el token.

**Request:**
```json
{ "data": { "name": "Comida" } }
```

| Campo | Tipo | Requerido |
|-------|------|-----------|
| `name` | `string` | ✅ |

---

### `PATCH /api/v1/categories/{category_id}`

Actualiza una categoría.

**Request:**
```json
{ "data": { "name": "Alimentación" } }
```

---

### `DELETE /api/v1/categories/{category_id}`

Elimina una categoría.

---

## Tags

> **Ruta base:** `/api/v1/tags`

### `GET /api/v1/tags`

Lista todos los tags del usuario.

---

### `GET /api/v1/tags/{tag_id}`

Obtiene un tag específico.

---

### `POST /api/v1/tags`

Crea un nuevo tag. `user_id` se asigna desde el token.

**Request:**
```json
{ "data": { "name": "Urgente" } }
```

---

### `PATCH /api/v1/tags/{tag_id}`

Actualiza un tag.

**Request:**
```json
{ "data": { "name": "Importante" } }
```

---

### `DELETE /api/v1/tags/{tag_id}`

Elimina un tag.

---

## Esquemas de respuesta

### WalletResponseSerializer

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `uuid` | Identificador único |
| `user_id` | `string` | ID del usuario propietario |
| `name` | `string` | Nombre de la wallet |
| `balance` | `float` | Saldo actual |
| `created_at` | `datetime` | Fecha de creación |
| `updated_at` | `datetime` | Última actualización |

### TransactionResponseSerializer

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `uuid` | Identificador único |
| `user_id` | `string` | ID del usuario propietario |
| `title` | `string` | Título |
| `description` | `string` | Descripción |
| `amount` | `float` | Monto |
| `type` | `string` | `"income"` o `"expense"` |
| `wallet_id` | `uuid` | ID de la wallet asociada |
| `category_id` | `uuid` | ID de la categoría asociada |
| `created_at` | `datetime` | Fecha de creación |
| `updated_at` | `datetime` | Última actualización |

### CategoryResponseSerializer / TagResponseSerializer

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `uuid` | Identificador único |
| `user_id` | `string` | ID del usuario propietario |
| `name` | `string` | Nombre |
| `created_at` | `datetime` | Fecha de creación |
| `updated_at` | `datetime` | Última actualización |

---

## Códigos de error

| Código | Descripción |
|--------|-------------|
| `400` | Solicitud mal formada |
| `401` | Token JWT inválido o ausente |
| `403` | Usuario no es propietario del recurso |
| `404` | Recurso no encontrado |
| `422` | Error de validación en el cuerpo de la solicitud |
