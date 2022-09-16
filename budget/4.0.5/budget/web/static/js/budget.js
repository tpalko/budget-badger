function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function handleDeleteClick(e) {

	e.preventDefault();

	if(!confirm("Are you sure?")){
		return false;
	}

	// fetch(e.target.getAttribute("href"))
	// 	.then((response) => {
	// 		var elementId = e.target.dataset['elementId'];
	// 		console.log("Removing " + elementId);
	// 		(document.querySelector("#" + elementId) && document.querySelector("#" + elementId).remove()) || console.log("No such ID exists!");
	// 	})
	// 	.catch((error) => {
	// 		addErrorMessage(error);
	// 	});

	var csrftoken = getCookie('csrftoken');

	options = {
		method: 'DELETE',
		headers: {
			"X-CSRFToken": csrftoken
		}
	}
	fetch(e.target.href, options)
		.then((response) => {
			document.location = document.location;
		})
		.catch((error) => {
			alert(error);
		});

	return true;
}

document.querySelector(".delete") && document.querySelectorAll(".delete").forEach((el, i) => {
	if (!el.classList.contains('noconfirm')) {
		el.addEventListener("click", handleDeleteClick);
	}	
});

function addErrorMessage(message) {
	var newMessage = document.createElement("li");
	newMessage.innerHTML = message;
	document.querySelector("ul.messages").appendChild(newMessage);
}

function initTabs() {

	document.querySelectorAll("ul.tabs").forEach((tabsUl, i) => {
		
		var tabsId = tabsUl.getAttribute('id');

		document.querySelectorAll("div[id^=" + tabsId + "-]").forEach((el, i) => {
			el.classList.add('hidden');
		})
		
		tabsUl.querySelectorAll("li").forEach((tabsLi, i) => {
			tabsLi.addEventListener('click', (e) => {
			
				var clickedId = e.target.getAttribute('id');
				
				tabsUl.querySelectorAll("li").forEach((subTabsLi, i) => {
					var tabId = subTabsLi.getAttribute('id');
					if (clickedId == tabId) {
						subTabsLi.classList.add('selected');
					} else {
						subTabsLi.classList.remove('selected');
					}
				})
	
				document.querySelectorAll("div[id^=" + tabsId + "-]").forEach((contentEl, i) => {
					var replaceStr = /tabs-records-/
					var contentId = contentEl.getAttribute('id').replace(replaceStr, "");
					if(contentId != clickedId) {
						contentEl.classList.add('hidden');
					} else {
						contentEl.classList.remove('hidden');
					}
				});	
			});
		});
		
		tabsUl.querySelector("li[id=" + tabsUl.dataset['default'] + "]").click();
	});
}

document.addEventListener('DOMContentLoaded', function() {

	initTabs();

	document.querySelectorAll(".collapse-title").forEach((el, i) => {
		var collapseId = el.getAttribute('id');
		var collapseElements = document.querySelectorAll("." + collapseId);
		el.addEventListener('click', (e) => {
			e.preventDefault();
			collapseElements.forEach((collapseEl, j) => {
				if (collapseEl.classList.contains('hidden')) {
					collapseEl.classList.remove('hidden');
				} else {
					collapseEl.classList.add('hidden');
				}				
			});
		});
	})

	// document.querySelectorAll("input[id$=_at]").forEach( (i, e) => {
	// 	$("#" + e.id).datepicker({dateFormat: "yy-mm-dd", showButtonPanel: true});	
	// });

	// // using jQuery
	// function getCookie(name) {
	//     var cookieValue = null;
	//     if (document.cookie && document.cookie != '') {
	//         var cookies = document.cookie.split(';');
	//         for (var i = 0; i < cookies.length; i++) {
	//             var cookie = jQuery.trim(cookies[i]);
	//             // Does this cookie string begin with the name we want?
	//             if (cookie.substring(0, name.length + 1) == (name + '=')) {
	//                 cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
	//                 break;
	//             }
	//         }
	//     }
	//     return cookieValue;
	// }
         
	// var csrftoken = getCookie('csrftoken');
	// function csrfSafeMethod(method) {
	//     // these HTTP methods do not require CSRF protection
	//     return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
	// }

	// $.ajaxSetup({
	//     beforeSend: function(xhr, settings) {
	//         if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
	//             xhr.setRequestHeader("X-CSRFToken", csrftoken);
	//         }
	//     }
	// });
});