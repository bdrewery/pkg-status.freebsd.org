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

function filter_icon() {
    return '<span class="glyphicon glyphicon-filter"></span>';
}

function poudriere_icon() {
    return '<img src="' + Flask.url_for('static', {'filename': 'poudriere.png'}) + '">';
}

function linkpoudrierebuild(build) {
    return '<a target="_new" data-toggle="tooltip" title="Poudriere Build" ' +
        'href="http://' + servers[build.server].host +
        '/build.html?mastername=' + build.mastername +
        '&amp;build=' + build.buildname + '">' + poudriere_icon() + '</a>';
}

function linkbuild(build) {
    return '<a data-toggle="tooltip" title="All builds matching buildname ' +
        build.buildname + '" href="' +
        Flask.url_for('builds', {'buildname': build.buildname}) + '">' +
        filter_icon() + '</a>' +
        linkpoudrierebuild(build) +
        '<a data-toggle="tooltip" title"Build ' + build._id + '" href="' +
        Flask.url_for('build', {'buildid': build._id}) + '">' +
        build.buildname + '</a>';
}

function isNumeric(n) {
    return !isNaN(parseFloat(n)) && isFinite(n);
}

function linkset(setname) {
    var link;

    if (!setname)
        setname = "default";

    if (setname.substring(0, 2).toUpperCase() == "PR" &&
            isNumeric(setname.substring(2))) {
        link = "http://bugs.FreeBSD.org/" + setname.substring(2);
    } else if (isNumeric(setname)) {
        link = "http://bugs.FreeBSD.org/" + setname;
    } else if (setname.substring(0, 1).toUpperCase() == "D" &&
            isNumeric(setname.substring(1))) {
        link = "https://reviews.FreeBSD.org/" + setname;
    }
    if (link) {
        link =  '<a data-toggle="tooltip" title="Related issue" href="' +
            link + '"><span class="glyphicon glyphicon-share-alt"></span></a>';
    } else
        link = '';
    return '<a data-toggle="tooltip" title="All builds matching set ' +
        setname + '" href="' + Flask.url_for('builds', {'setname': setname}) +
        '"><span class="glyphicon glyphicon-filter"></span></a>' +
        link + setname;
}

function linkserver(build) {
    return '<a data-toggle="tooltip" title="All builds matching server ' +
    build.server + '" href="' +
    Flask.url_for('builds', {'server': build.server}) + '">' +
    filter_icon() + '</a>' +
    '<a target="_new" data-toggle="tooltip" title="Poudriere Server" ' +
    'href="http://' + servers[build.server].host + '/">' +
    poudriere_icon() + '</a>' +
    build.server;
}

function linkjail(build) {
    return '<a data-toggle="tooltip" title="All builds matching jail ' +
    build.jailname + '" href="' +
    Flask.url_for('builds', {'jailname': build.jailname}) + '">' +
    filter_icon() + '</a>' +
    '<a target="_new" data-toggle="tooltip" title="Poudriere Jail" ' +
    'href="http://' + servers[build.server].host +
    '/jail.html?mastername=' + build.mastername + '">' + poudriere_icon() +
    '</a>' + build.jailname;
}

function format_duration(duration) {
    if (duration < 0) {
        duration = 0;
    }

    hours = Math.floor(duration / 3600);
    duration = duration - hours * 3600;
    minutes = Math.floor(duration / 60);
    seconds = duration - minutes * 60;

    if (hours < 10) {
        hours = '0' + hours;
    }
    if (minutes < 10) {
        minutes = '0' + minutes;
    }
    if (seconds < 10) {
        seconds = '0' + seconds;
    }

    return hours + ':' + minutes + ':' + seconds;
}

function format_stats(value, build, colname) {
    var html;

    html = value;
    if (build.new_stats && build.new_stats[colname]) {
        html += '&nbsp<a href="' +
            Flask.url_for('build', {'buildid': build._id}) +
            '#new_' + colname + '"> (+' + build.new_stats[colname] + ')</a>';
    }
    return html;
}

function format_datetime(epoch) {
    var date = new Date(parseInt(epoch) * 1000);
    return date.toUTCString();
}

function dt_format(formatter, colname, data, type, full, meta) {
    switch (formatter) {
        case "datetime":
            if (type == "sort")
                return parseInt(data);
            return format_datetime(data);
        case "duration":
            if (type == "sort")
                return parseInt(data);
            return format_duration(data);
        case "linkbuild":
            return linkbuild(full);
        case "linkjail":
            return linkjail(full);
        case "linkset":
            return linkset(data);
        case "linkserver":
            return linkserver(full);
        case "stats":
            if (data === undefined)
                data = 0;
            if (type == "filter")
                return false;
            else if (type == "sort")
                return parseInt(data);
            return format_stats(data, full, colname.substring(6));
        default:
            return formatter + ' ' + data;
    }
}

$(function () {
  $('[data-datatable="true"]').each(function() {
      var config = {}, columnDef, config, columns;

      if ($(this).data("dt-url")) {
          columns = $(this).find('[data-dt-col]').map(function() {
              columnDef = {
                  "data": $(this).data("dt-col"),
                  "defaultContent": "",
              };
              if ($(this).data("dt-col-type")) {
                  columnDef['type'] = $(this).data("dt-col-type");
              }
              if ($(this).data("dt-col-formatter")) {
                  var formatter = $(this).data("dt-col-formatter");
                  var colname = $(this).data("dt-col");
                  columnDef["render"] = function(data, type, full, meta) {
                      return dt_format(formatter, colname, data, type, full, meta);
                  };
              }
              return columnDef;
          }).get();
          config = {
              "ajax": {"url":$(this).data("dt-url")},
              "columns": columns,
              "processing": true,
          };
          if ($(this).data("dt-datasrc")) {
              config['ajax']['dataSrc'] = $(this).data("dt-datasrc");
          }
      }
      $(this).dataTable(config).show();
  });
})
