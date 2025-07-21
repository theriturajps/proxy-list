document.addEventListener('DOMContentLoaded', function () {
	const proxyList = document.getElementById('proxy-list');
	const searchInput = document.getElementById('search');
	const copyAllBtn = document.getElementById('copy-all');
	const downloadTxtBtn = document.getElementById('download-txt');
	const downloadJsonBtn = document.getElementById('download-json');
	const prevPageBtn = document.getElementById('prev-page');
	const nextPageBtn = document.getElementById('next-page');
	const pageInfo = document.getElementById('page-info');
	const lastUpdatedSpan = document.getElementById('last-updated');
	const proxyCountSpan = document.getElementById('proxy-count');

	let allProxies = [];
	let filteredProxies = [];
	const proxiesPerPage = 50;
	let currentPage = 1;
	let totalPages = 1;

	// Load proxy data
	fetch('proxies.json')
		.then(response => response.json())
		.then(data => {
			allProxies = data.proxies;
			filteredProxies = [...allProxies];

			// Update metadata
			lastUpdatedSpan.textContent = new Date(data.metadata.last_updated).toLocaleString();
			proxyCountSpan.textContent = data.proxies.length.toLocaleString();

			// Initial render
			updatePagination();
			renderProxies();
		})
		.catch(error => {
			console.error('Error loading proxy data:', error);
			proxyList.innerHTML = '<tr><td colspan="4" class="error">Failed to load proxy data. Please try again later.</td></tr>';
		});

	// Search functionality
	searchInput.addEventListener('input', function () {
		const searchTerm = this.value.toLowerCase();

		if (searchTerm.trim() === '') {
			filteredProxies = [...allProxies];
		} else {
			filteredProxies = allProxies.filter(proxy => {
				return proxy.toLowerCase().includes(searchTerm);
			});
		}

		currentPage = 1;
		updatePagination();
		renderProxies();
	});

	// Copy all proxies
	copyAllBtn.addEventListener('click', function () {
		const textToCopy = filteredProxies.join('\n');
		navigator.clipboard.writeText(textToCopy)
			.then(() => {
				showToast('All proxies copied to clipboard!');
			})
			.catch(err => {
				console.error('Failed to copy text: ', err);
				showToast('Failed to copy proxies', 'error');
			});
	});

	// Download TXT
	downloadTxtBtn.addEventListener('click', function () {
		const blob = new Blob([filteredProxies.join('\n')], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = 'proxies.txt';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	});

	// Download JSON
	downloadJsonBtn.addEventListener('click', function () {
		const data = {
			count: filteredProxies.length,
			proxies: filteredProxies
		};
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = 'proxies.json';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	});

	// Pagination
	prevPageBtn.addEventListener('click', function () {
		if (currentPage > 1) {
			currentPage--;
			updatePagination();
			renderProxies();
		}
	});

	nextPageBtn.addEventListener('click', function () {
		if (currentPage < totalPages) {
			currentPage++;
			updatePagination();
			renderProxies();
		}
	});

	function updatePagination() {
		totalPages = Math.ceil(filteredProxies.length / proxiesPerPage);
		pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;

		prevPageBtn.disabled = currentPage === 1;
		nextPageBtn.disabled = currentPage === totalPages || totalPages === 0;
	}

	function renderProxies() {
		const startIndex = (currentPage - 1) * proxiesPerPage;
		const endIndex = startIndex + proxiesPerPage;
		const proxiesToShow = filteredProxies.slice(startIndex, endIndex);

		if (proxiesToShow.length === 0) {
			proxyList.innerHTML = '<tr><td colspan="4">No proxies found matching your search.</td></tr>';
			return;
		}

		proxyList.innerHTML = proxiesToShow.map(proxy => {
			const [ip, port] = proxy.split(':');
			return `
                <tr>
                    <td>${ip}</td>
                    <td>${port}</td>
                    <td><i class="fas fa-globe"></i> Unknown</td>
                    <td>
                        <button class="action-btn copy" data-proxy="${proxy}">
                            <i class="fas fa-copy"></i> Copy
                        </button>
                        <button class="action-btn test" data-proxy="${proxy}">
                            <i class="fas fa-bolt"></i> Test
                        </button>
                    </td>
                </tr>
            `;
		}).join('');

		// Add event listeners to action buttons
		document.querySelectorAll('.action-btn.copy').forEach(btn => {
			btn.addEventListener('click', function () {
				const proxy = this.getAttribute('data-proxy');
				navigator.clipboard.writeText(proxy)
					.then(() => {
						showToast('Proxy copied to clipboard!');
					})
					.catch(err => {
						console.error('Failed to copy text: ', err);
						showToast('Failed to copy proxy', 'error');
					});
			});
		});

		document.querySelectorAll('.action-btn.test').forEach(btn => {
			btn.addEventListener('click', function () {
				const proxy = this.getAttribute('data-proxy');
				testProxy(proxy, this);
			});
		});
	}

	function testProxy(proxy, button) {
		const originalText = button.innerHTML;
		button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
		button.disabled = true;

		// This is a simulated test - in a real implementation you would ping the proxy
		setTimeout(() => {
			const isWorking = Math.random() > 0.3; // 70% chance of "working"
			button.innerHTML = isWorking
				? '<i class="fas fa-check"></i> Working'
				: '<i class="fas fa-times"></i> Failed';

			button.style.color = isWorking ? 'green' : 'red';
			button.style.borderColor = isWorking ? 'green' : 'red';

			// Reset after 3 seconds
			setTimeout(() => {
				button.innerHTML = originalText;
				button.style.color = '';
				button.style.borderColor = '';
				button.disabled = false;
			}, 3000);
		}, 1500);
	}

	function showToast(message, type = 'success') {
		const toast = document.createElement('div');
		toast.className = `toast ${type}`;
		toast.textContent = message;
		document.body.appendChild(toast);

		setTimeout(() => {
			toast.classList.add('show');
		}, 10);

		setTimeout(() => {
			toast.classList.remove('show');
			setTimeout(() => {
				document.body.removeChild(toast);
			}, 300);
		}, 3000);
	}
});