$(function () {
  $('[data-toggle="tooltip"]').tooltip({'placement': 'bottom'});
})

$.extend( $.fn.dataTable.defaults, {
    autoWidth: false,
    deferRender: true,
    lengthMenu: [[5,10,15,25,50,100,200, -1],[5,10,15,25,50,100,200,"All"]],
    pageLength: 15,
    orderClasses: true,
    renderer: "bootstrap",
    stateSave: false
});

$(function () {
  $('[data-datatable="true"]').dataTable().show();
})
