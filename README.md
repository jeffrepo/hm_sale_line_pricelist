# HM — Listas de precios por línea en Ventas

Módulo para **Odoo 18.0**, Community y Enterprise. Permite seleccionar una lista
de precios en cada línea de una cotización o pedido. Depende de `sale`; no
requiere el módulo de POS ni el desarrollo de remisiones de HM Express.

## Instalación

1. Clonar este repositorio como `hm_sale_line_pricelist` dentro de una carpeta
   incluida en `addons_path`.
2. Reiniciar Odoo, actualizar la lista de aplicaciones e instalar
   **HM - Listas de precios por línea en Ventas**. Quitar el filtro «Aplicaciones»
   para encontrarlo, ya que es una extensión.
3. Activar **Listas de precios** en la configuración de Ventas y crear las tarifas.

```sh
git clone https://github.com/jeffrepo/hm_sale_line_pricelist.git
odoo-bin -d BASE -i hm_sale_line_pricelist --stop-after-init
```

Para actualizar una instalación existente, utilizar `-u hm_sale_line_pricelist`.

## Uso

La columna **Lista de precios** aparece antes de **Precio unitario**. Vacía
significa «usar la lista del pedido». Elegir una lista calcula el precio con el
motor de Odoo, incluyendo reglas por producto, categoría, cantidad, fecha,
fórmulas, descuentos, unidad de medida, atributos e impuestos.

- Cambiar la cantidad actualiza el precio conforme a la tarifa de la línea.
- Borrar la selección vuelve a la lista del pedido.
- Elegir expresamente una tarifa reemplaza un precio previamente escrito a mano.
- Si después se escribe un precio manual, Odoo conserva su comportamiento normal.
- El botón nativo **Actualizar precios** respeta las listas específicas de cada
  línea. Cambiar únicamente la lista del encabezado conserva el comportamiento
  nativo de Ventas: usar ese botón para actualizar las líneas existentes.
- Las líneas duplicadas conservan la selección. La factura recibe el precio y
  descuento resultantes mediante el flujo normal de Odoo.
- Las listas deben tener la misma moneda del pedido y pertenecer a su compañía
  o ser compartidas. No se cambia la moneda de una línea individual.
- No se permite cambiar la tarifa en líneas facturadas ni pedidos bloqueados.
- En combos se selecciona en el producto principal; Odoo distribuye su precio
  entre los componentes. Notas, anticipos y gastos conservan su cálculo propio.

El campo persistente es `sale.order.line.line_pricelist_id` (`product.pricelist`).
No se crean nuevas listas ni se modifica la lista del encabezado al seleccionar
una tarifa en una línea.

## Pruebas

En una base de pruebas, con el directorio padre del módulo en `addons_path`:

```sh
odoo-bin -d PRUEBAS -i hm_sale_line_pricelist --test-enable \
  --test-tags /hm_sale_line_pricelist --stop-after-init
```

La suite cubre selección desde el formulario, cantidades, restablecimiento,
actualización general, precios manuales, descuentos, impuestos incluidos,
valores de facturación, duplicación, moneda, compañía y pedidos bloqueados.
GitHub Actions ejecuta estas pruebas con Odoo 18 y PostgreSQL 16.

Licencia: LGPL-3.
