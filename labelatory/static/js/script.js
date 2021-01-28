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
            window.location = '/';
        }
    }
    xhr.send(data)

    console.log(name)
    console.log(color)
    console.log(description)

}
