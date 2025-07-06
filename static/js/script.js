document.addEventListener('DOMContentLoaded', () => {
    const toggleUploadFormBtn = document.getElementById('toggleUploadFormBtn');
    const uploadArea = document.getElementById('upload-area');
    const uploadForm = document.getElementById('uploadForm');
    const messageDiv = document.getElementById('message');
    const imageUploadInput = document.getElementById('imageUpload');
    const titleInput = document.getElementById('titleInput');
    const descInput = document.getElementById('descInput');
    const cardsContainer = document.getElementById('cardsContainer');
    const noDrawingsMessage = document.getElementById('noDrawingsMessage');

    const imageModal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImg');
    const modalTitle = document.getElementById('modalTitle');
    const modalDesc = document.getElementById('modalDesc');
    const closeModalBtn = document.getElementById('closeModalBtn');

    // --- Lógica para mostrar/esconder o formulário de upload ---
    if (toggleUploadFormBtn) {
        toggleUploadFormBtn.addEventListener('click', () => {
            uploadArea.style.display = uploadArea.style.display === 'flex' ? 'none' : 'flex';
            messageDiv.textContent = '';
        });
    }

    // --- Lógica para envio do formulário de upload via AJAX ---
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const file = imageUploadInput.files[0];
            if (!file) {
                messageDiv.textContent = 'Por favor, selecione um arquivo para upload.';
                messageDiv.style.color = 'orange';
                return;
            }

            const formData = new FormData();
            formData.append('image', file);
            formData.append('title', titleInput.value);
            formData.append('description', descInput.value);

            messageDiv.textContent = 'Enviando desenho...';
            messageDiv.style.color = 'blue';

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    messageDiv.textContent = data.message;
                    messageDiv.style.color = 'green';

                    imageUploadInput.value = '';
                    titleInput.value = '';
                    descInput.value = '';
                    uploadArea.style.display = 'none';

                    loadImages(); // Recarrega todas as imagens após um novo upload

                } else {
                    messageDiv.textContent = `Erro: ${data.message || 'Ocorreu um erro ao enviar.'}`;
                    messageDiv.style.color = 'red';
                }
            } catch (error) {
                console.error('Erro no upload:', error);
                messageDiv.textContent = 'Erro de conexão ou servidor.';
                messageDiv.style.color = 'red';
            }
        });
    }

    // --- Lógica para o Modal ---
    function openModal(src, title, desc) {
        modalImg.src = src;
        modalTitle.textContent = title;
        modalDesc.textContent = desc;
        imageModal.style.display = 'flex';
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            imageModal.style.display = 'none';
        });
    }

    // Fecha o modal clicando fora
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) {
            imageModal.style.display = 'none';
        }
    });

    // --- Nova Função: Carregar e Renderizar Imagens do Servidor ---
    async function loadImages() {
        try {
            const response = await fetch('/api/images');
            if (!response.ok) {
                throw new Error(`Erro HTTP: ${response.status}`);
            }
            const images = await response.json();

            cardsContainer.innerHTML = ''; // Limpa o container antes de adicionar novas imagens

            if (images.length === 0) {
                if (noDrawingsMessage) {
                    cardsContainer.appendChild(noDrawingsMessage);
                    noDrawingsMessage.style.display = 'block';
                }
            } else {
                if (noDrawingsMessage) {
                    noDrawingsMessage.style.display = 'none';
                }

                images.forEach(image => {
                    const cardHtml = `
                        <div class="card" data-full-src="${image.filepath}" data-title="${image.title}" data-description="${image.description}" data-id="${image.id}">
                            <span class="delete-btn" data-id="${image.id}">&times;</span>
                            <img src="${image.filepath}" alt="${image.title || image.filename}">
                            <div class="card-info">
                                <div class="card-title">${image.title || image.filename}</div>
                                ${image.description ? `<div class="card-description">${image.description}</div>` : ''}
                                <small class="card-date">Enviado: ${new Date(image.upload_date).toLocaleDateString('pt-BR')}</small>
                            </div>
                        </div>
                    `;
                    cardsContainer.insertAdjacentHTML('beforeend', cardHtml);
                });
                // Removida a chamada para addCardClickListeners() aqui,
                // pois o listener principal no cardsContainer já gerencia os cliques.
            }

        } catch (error) {
            console.error('Falha ao carregar imagens:', error);
            cardsContainer.innerHTML = `<p style="text-align: center; color: red;">Erro ao carregar desenhos: ${error.message}</p>`;
        }
    }

    // --- Lógica para adicionar listeners de clique aos cards (para modal e exclusão) ---
    // Este é o ÚNICO listener para cards, e ele delega a ação.
    cardsContainer.addEventListener('click', (event) => {
        const card = event.target.closest('.card');
        if (!card) return;

        if (event.target.classList.contains('delete-btn')) {
            const imageId = card.dataset.id;
            if (confirm('Tem certeza que deseja excluir este desenho? Esta ação não pode ser desfeita.')) {
                fetch(`/delete/${imageId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        loadImages();
                    } else {
                        alert('Erro ao excluir desenho: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Erro na requisição de exclusão:', error);
                    alert('Ocorreu um erro ao tentar excluir o desenho.');
                });
            }
        } else {
            const src = card.dataset.fullSrc;
            const title = card.dataset.title;
            const description = card.dataset.description;
            openModal(src, title, description);
        }
    });

    // --- Chamar a função de carregamento de imagens quando a página é carregada ---
    loadImages();
});