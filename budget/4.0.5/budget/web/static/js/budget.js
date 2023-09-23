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
		.then((response) => response.json())
		.then((responsej) => {

			console.log('recieved response from delete call');
			console.log(responsej);
			var callback = e.target.dataset.deletecallback;

			if (callback) {
				console.log('looking for ' + callback + ' in window');
				console.log(window[callback]);
				window[callback](responsej);
			} else {
				console.log("delete response received but no 'deletecallback' defined, so refreshing on " + document.location);
				document.location = document.location;
			}
			
		})
		.catch((error) => {
			console.error('error caught in delete fetch');
			console.error(error);
			alert(error);
		});

	return true;
}

function addErrorMessage(message) {
	var newMessage = document.createElement("li");
	newMessage.innerHTML = message;
	document.querySelector("ul.messages").appendChild(newMessage);
	document.querySelector("ul.messages").style.display = 'block';
	setTimeout(() => { 
		newMessage.remove(); 
		if (document.querySelectorAll("ul.messages li").length == 0) { 
			document.querySelector("ul.messages").style.display = 'none'; 
		} 
	}, 5000);	
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
					var replaceStr = tabsId + "-"
					var contentId = contentEl.getAttribute('id').replace(replaceStr, "");
					if(contentId != clickedId) {
						contentEl.classList.add('hidden');
					} else {
						contentEl.classList.remove('hidden');
					}
				});	
			});
		});
		
		if (tabsUl.dataset.default) {
			tabsUl.querySelector("li[id=" + tabsUl.dataset.default + "]").click();
		} else {
			tabsUl.querySelectorAll("li")[0].click();
		}
	});
}

function clickyTableClick(e) {
	
	if (e.target.dataset.clickyrow) {
		document.querySelector("tr#" + e.target.dataset.clickyrow).classList.add("selected");
	}	
}

document.addEventListener('DOMContentLoaded', function() {

	initTabs();

	document.querySelector(".delete") && document.querySelectorAll(".delete").forEach((el, i) => {
		if (!el.classList.contains('noconfirm')) {
			el.addEventListener("click", handleDeleteClick);
		}	
	});

	document.querySelectorAll(".intercept_to_target").forEach((el, i) => {
		el.addEventListener('click', (e) => {
			e.preventDefault();
			fetch(e.target.href, options)
				.then((response) => response.json())
				.then((data) => {
					if (data.success) {
						document.querySelector(el.dataset.target).innerHTML = data.data.html;
					}
				})
				.catch((error) => {
					alert(error);
				})
			return false;
		})
	})
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

	document.querySelectorAll("table.clicky-table tr").forEach((el, i) => {
		el.addEventListener('click', clickyTableClick);
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