/** @typedef {{id:number, title:string, payload:object, author:string}} BusinessCase */
/** @typedef {{id:number, case_id:number, status:'queued'|'running'|'complete'|'failed'}} Run */
/** @typedef {{id:number, run_id:number, digest:string, report:{summary:string, metrics:object, sections:Array}}} Evidence */
/** @typedef {{id:number, number:number, title:string, available_copies:number}} CatalogScore */
/** @typedef {{id:number, base_version:number, result_version:number|null, status:'applied'|'rejected', reason:string|null, items:Array, actor:string, created_at:string}} RenumberOrder */
/** @typedef {{id:number, range_start:number, range_end:number, catalog_version:number, actor:string, created_at:string}} BorrowSlip */
/** @typedef {BorrowSlip & {current_version:number, rows:Array<{old_number:number, current_number:number, title:string, available_copies:number}>}} BorrowSlipDetail */
