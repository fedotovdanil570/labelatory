function addLabel(link){
    
    var name = document.getElementById('label-name').value
    var color = document.getElementById('label-color').value
    var description = document.getElementById('label-description').value

    if(!name){
        alert("Label name is not specified!")
        return
    }
    if(!color){
        alert("Label color is not specified!")
        return
    }
    if(!description){
        alert("Label description is not specified!")
        return
    }

    regex = new RegExp(/^#[0-9a-f]{6}/i);
    res = regex.test(color)
    if(!res){
        alert("Label color has whong format. Must be like #ffffff.")
        return
    }

    var xhr = new XMLHttpRequest()

    var data = JSON.stringify({
        name:name,
        color:color,
        description:description
    })

    xhr.open('POST', link, true)
    xhr.setRequestHeader('Content-type', 'application/json; charset=utf-8')
    xhr.onreadystatechange = function(){
        if (this.readyState == 4){
            var resp_type = xhr.getResponseHeader("Content-Type")
            if (resp_type == 'application/json'){
                var resp = JSON.parse(xhr.response)
                alert(resp.error)
                return
            }

            
            window.location = xhr.responseURL;

            return;
        }
    }
    xhr.send(data)

    // console.log(name)
    // console.log(color)
    // console.log(description)

}

function editLabel(link, oldName){
    // console.log(label)
    var name = document.getElementById('label-name').value
    var color = document.getElementById('label-color').value
    var description = document.getElementById('label-description').value

    if(!name){
        alert("Label name is not specified!")
        return
    }
    if(!color){
        alert("Label color is not specified!")
        return
    }
    if(!description){
        alert("Label description is not specified!")
        return
    }

    regex = new RegExp(/^#[0-9a-f]{6}/i);
    res = regex.test(color)
    if(!res){
        alert("Label color has whong format. Must be like #ffffff.")
        return
    }

    var xhr = new XMLHttpRequest()

    var data = JSON.stringify({
        name:name,
        oldName:oldName,
        color:color,
        description:description
    })

    xhr.open('PUT', link, true)
    xhr.setRequestHeader('Content-type', 'application/json; charset=utf-8')
    xhr.onreadystatechange = function(){
        if (this.readyState == 4){
            window.location = xhr.responseURL;
            return;
        }
    }
    xhr.send(data)

}

function deleteLabel(labelName){
    var xhr = new XMLHttpRequest()

    var data = JSON.stringify({
        name: labelName
    })

    xhr.open('DELETE', '/', true)
    xhr.setRequestHeader('Content-type', 'application/json; charset=utf-8')
    xhr.onreadystatechange = function(){
        if (this.readyState == 4){
            var resp_type = xhr.getResponseHeader("Content-Type")
            if (resp_type == 'application/json'){
                var resp = JSON.parse(xhr.response)
                alert(resp.error)
                return
            }
            window.location = '/';
            return;
        }
    }
    xhr.send(data)
}

function switchServiceState(service, reposlug, enabled){
    if (enabled == 'True'){
        enabled = 'False'
    }else{
        enabled = 'True'
    }

    var xhr = new XMLHttpRequest()

    var data = JSON.stringify({
        service:service,
        reposlug:reposlug,
        enabled:enabled
    })

    xhr.open('POST', '/', true)
    xhr.setRequestHeader('Content-type', 'application/json; charset=utf-8')
    xhr.onreadystatechange = function(){
        if (this.readyState == 4){
            var resp_type = xhr.getResponseHeader("Content-Type")
            if (resp_type == 'application/json'){
                var resp = JSON.parse(xhr.response)
                alert(resp.error)
                return
            }
            window.location = '/';
            return;
        }
    }
    xhr.send(data)
}
