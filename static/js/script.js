document.addEventListener('DOMContentLoaded', () => {
    const toggleUploadFormBtn = document.getElementById('toggleUploadFormBtn');
    const uploadArea = document.getElementById('upload-area');
    const uploadForm = document.getElementById('uploadForm');
    const messageDiv = document.getElementById('message');
    const imageUploadInput = document.getElementById('imageUpload');
    const titleInput = document.getElementById('titleInput');
    const descInput = document.getElementById('descInput');
    const cardsContainer = document.getElementById('cardsContainer');

    const imageModal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImg');
    const modalTitle = document.getElementById('modalTitle');
    const modalDesc = document.getElementById('modalDesc');
    const closeModalBtn = document.getElementById('closeModalBtn');

    // --- Lógica para mostrar/esconder o formulário de upload ---
    if (toggleUploadFormBtn) {
        toggleUploadFormBtn.addEventListener('click', () => {
            uploadArea.style.display = uploadArea.style.display === 'flex' ? 'none' : 'flex';
            messageDiv.textContent = ''; // Limpa mensagens ao abrir/fechar
        });
    }

    // --- Lógica para envio do formulário de upload via AJAX ---
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (event) => {
            event.preventDefault(); // Impede o envio padrão do formulário

            const file = imageUploadInput.files[0];
            if (!file) {
                messageDiv.textContent = 'Por favor, selecione um arquivo para upload.';
                messageDiv.style.color = 'orange';
                return;
            }

            const formData = new FormData();
            formData.append('image', file);
            formData.append('title', titleInput.value);       // Adiciona o título
            formData.append('description', descInput.value); // Adiciona a descrição

            messageDiv.textContent = 'Enviando desenho...';
            messageDiv.style.color = 'blue';

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json(); // Pega a resposta JSON do Flask

                if (response.ok) { // Verifica se a resposta HTTP foi bem-sucedida (código 2xx)
                    messageDiv.textContent = data.message;
                    messageDiv.style.color = 'green';

                    // Limpa o formulário
                    imageUploadInput.value = '';
                    titleInput.value = '';
                    descInput.value = '';
                    uploadArea.style.display = 'none'; // Esconde o formulário após o sucesso

                    // Adiciona a nova imagem à galeria dinamicamente
                    // A data de upload será a data atual do cliente para exibição imediata
                    const uploadDate = new Date().toLocaleDateString('pt-BR');
                    const newImageHtml = `
                        <div class="card" data-full-src="${data.image_url}" data-title="${titleInput.value}" data-description="${descInput.value}">
                            <img src="${data.image_url}" alt="${data.filename}">
                            <div class="card-title">${titleInput.value || data.filename}</div>
                            </div>
                    `;

                    // Se a mensagem "Nenhum desenho ainda." estiver presente, remova-a
                    const noDrawingsMessage = cardsContainer.querySelector('p');
                    if (noDrawingsMessage && noDrawingsMessage.textContent.includes('Nenhum desenho ainda.')) {
                        noDrawingsMessage.remove();
                    }
                    cardsContainer.insertAdjacentHTML('afterbegin', newImageHtml); // Adiciona a imagem no início da galeria

                    // Re-adiciona os event listeners para os novos cards
                    addCardClickListeners();

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

    // Função para adicionar listeners de clique aos cards (para o modal)
    function addCardClickListeners() {
        document.querySelectorAll('.card').forEach(card => {
            // Remove o listener anterior para evitar duplicação (se já houver)
            card.removeEventListener('click', handleCardClick);
            // Adiciona o novo listener
            card.addEventListener('click', handleCardClick);
        });
    }

    // Manipulador de clique para os cards
    function handleCardClick(event) {
        const card = event.currentTarget; // O card que foi clicado
        const src = card.dataset.fullSrc;
        const title = card.dataset.title;
        const description = card.dataset.description;
        openModal(src, title, description);
    }

    // Adiciona listeners para os cards existentes na carga inicial da página
    addCardClickListeners();

});

// ... (seu código existente para upload e toggle do formulário) ...

// Lógica para abrir o modal de imagem
document.getElementById('cardsContainer').addEventListener('click', function(event) {
    // Verifica se o clique foi em um card ou em uma imagem dentro de um card
    let card = event.target.closest('.card');
    if (card) {
        // Se o clique foi no botão de exclusão, lida com isso e não abre o modal
        if (event.target.classList.contains('delete-btn')) {
            const imageId = event.target.dataset.id;
            if (confirm('Tem certeza que deseja excluir este desenho? Esta ação não pode ser desfeita.')) {
                fetch(`/delete/${imageId}`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        // Recarregar a página para mostrar as imagens atualizadas
                        window.location.reload(); 
                    } else {
                        alert('Erro ao excluir desenho: ' + data.message);
                    }
                })
                .catch(error => {
                    console.error('Erro na requisição de exclusão:', error);
                    alert('Ocorreu um erro ao tentar excluir o desenho.');
                });
            }
            return; // Impede que o clique no botão de exclusão também abra o modal
        }

        // Se o clique não foi no botão de exclusão, abre o modal
        const imgSrc = card.querySelector('img').src;
        const imgTitle = card.dataset.title;
        const imgDesc = card.dataset.description;

        document.getElementById('modalImg').src = imgSrc;
        document.getElementById('modalTitle').textContent = imgTitle;
        document.getElementById('modalDesc').textContent = imgDesc;
        document.getElementById('imageModal').style.display = 'flex';
    }
});

// Lógica para fechar o modal
document.getElementById('closeModalBtn').addEventListener('click', function() {
    document.getElementById('imageModal').style.display = 'none';
    document.getElementById('modalImg').src = ''; // Limpa a imagem
    document.getElementById('modalTitle').textContent = ''; // Limpa o título
    document.getElementById('modalDesc').textContent = ''; // Limpa a descrição
});

// Fechar modal ao clicar fora do conteúdo
document.getElementById('imageModal').addEventListener('click', function(event) {
    if (event.target === this) { // Se o clique foi diretamente no modal (não no conteúdo)
        document.getElementById('imageModal').style.display = 'none';
        document.getElementById('modalImg').src = '';
        document.getElementById('modalTitle').textContent = '';
        document.getElementById('modalDesc').textContent = '';
    }
});