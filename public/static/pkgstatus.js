$(function () {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(tooltip => {
        new bootstrap.Tooltip(tooltip, { placement: 'bottom' });
    });
});

function flaskUrlFor(endpoint, params) {
    return '/' + endpoint + '?' + new URLSearchParams(params).toString();
}

function isNumeric(n) {
    return !isNaN(parseFloat(n)) && isFinite(n);
}

$.extend($.fn.dataTable.defaults, {
    autoWidth: false,
    deferRender: true,
    lengthMenu: [[5,10,15,25,50,100,200, -1],[5,10,15,25,50,100,200,"All"]],
    paging: true,
    pageLength: 15,
    orderClasses: true,
    stateSave: false,
    pagingType: 'full_numbers',
    renderer: "bootstrap"
});

function filter_icon() {
    return '<span class="bi bi-funnel-fill"></span>';
}

function poudriere_icon() {
    return '<img src="/static/poudriere.png">';
}

function linkpoudrierebuild(build) {
    return '<a target="_new" data-bs-toggle="tooltip" title="Poudriere Build" ' +
        'href="http://' + servers[build.server].host +
        '/build.html?mastername=' + build.mastername +
        '&amp;build=' + build.buildname + '">' + poudriere_icon() + '</a>';
}

function linkbuild(build) {
    return '<a data-bs-toggle="tooltip" title="All builds matching buildname ' +
        build.buildname + '" href="' +
        flaskUrlFor('builds', { 'buildname': build.buildname }) + '">' +
        filter_icon() + '</a>' +
        linkpoudrierebuild(build) +
        '<a data-bs-toggle="tooltip" title="Build ' + build._id + '" href="' +
        flaskUrlFor('build', { 'buildid': build._id }).replace('build?buildid=', 'builds/') + '">' +
        build.buildname + '</a>';
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
        link = '<a data-bs-toggle="tooltip" title="Related issue" href="' +
            link + '"><span class="bi bi-box-arrow-up-right"></span></a>';
    } else {
        link = '';
    }

    return '<a data-bs-toggle="tooltip" title="All builds matching set ' +
        setname + '" href="' + flaskUrlFor('builds', { 'setname': setname }) +
        '"><span class="bi bi-funnel-fill"></span></a>' +
        link + setname;
}

function linkserver(build) {
    return '<a data-bs-toggle="tooltip" title="All builds matching server ' +
    build.server + '" href="' +
    flaskUrlFor('builds', { 'server': build.server }) + '">' +
    filter_icon() + '</a>' +
    '<a target="_new" data-bs-toggle="tooltip" title="Poudriere Server" ' +
    'href="http://' + servers[build.server].host + '/">' +
    poudriere_icon() + '</a>' +
    build.server;
}

function linkjail(build) {
    return '<a data-bs-toggle="tooltip" title="All builds matching jail ' +
    build.jailname + '" href="' +
    flaskUrlFor('builds', { 'jailname': build.jailname }) + '">' +
    filter_icon() + '</a>' +
    '<a target="_new" data-bs-toggle="tooltip" title="Poudriere Jail" ' +
    'href="http://' + servers[build.server].host +
    '/jail.html?mastername=' + build.mastername + '">' + poudriere_icon() +
    '</a>' + build.jailname;
}

function format_duration(duration) {
    if (duration < 0) {
        duration = 0;
    }

    let hours = Math.floor(duration / 3600);
    duration = duration - hours * 3600;
    let minutes = Math.floor(duration / 60);
    let seconds = duration - minutes * 60;

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
            flaskUrlFor('build', { 'buildid': build._id }).replace('build?buildid=', 'builds/') +
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
    $('[data-datatable-html="true"]').DataTable({
        "paging": true,
        "ordering": true,
        "info": true,
        "searching": true
    });

    $('[data-datatable="true"]').each(function () {
        var columns = $(this).find('[data-dt-col]').map(function () {
            var columnDef = {
                "data": $(this).data("dt-col"),
                "defaultContent": "",
            };
            if ($(this).data("dt-col-type")) {
                columnDef['type'] = $(this).data("dt-col-type");
            }
            if ($(this).data("dt-col-formatter")) {
                var formatter = $(this).data("dt-col-formatter");
                var colname = $(this).data("dt-col");
                columnDef["render"] = function (data, type, full, meta) {
                    return dt_format(formatter, colname, data, type, full, meta);
                };
            }
            return columnDef;
        }).get();

        var config = {
            "processing": true,
            "serverSide": false,
            "ajax": {
                "url": $(this).data("dt-url"),
                "dataSrc": $(this).data("dt-datasrc") || ''
            },
            "columns": columns,
        };

        $(this).DataTable(config);
    });
});
