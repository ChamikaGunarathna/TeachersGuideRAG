async function handleSubmit(event) {
    event.preventDefault();
    
    const questionInput = document.getElementById('question');
    const submitBtn = document.getElementById('submit-btn');
    const buttonText = submitBtn.querySelector('.button-text');
    const loader = submitBtn.querySelector('.loader');
    const resultsContainer = document.querySelector('.results-container');
    const answerElement = document.getElementById('answer');
    const errorMessage = document.getElementById('error-message');
    
    // Disable input and show loading state
    questionInput.disabled = true;
    submitBtn.disabled = true;
    buttonText.style.display = 'none';
    loader.style.display = 'inline-block';
    errorMessage.style.display = 'none';
    
    try {
        const response = await fetch('/api/v1/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: questionInput.value
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get answer');
        }
        
        const data = await response.json();
        
        // Show the answer
        answerElement.textContent = data.answer;
        resultsContainer.style.display = 'block';
        
    } catch (error) {
        console.error('Error:', error);
        errorMessage.style.display = 'block';
        resultsContainer.style.display = 'none';
    } finally {
        // Reset the form state
        questionInput.disabled = false;
        submitBtn.disabled = false;
        buttonText.style.display = 'inline';
        loader.style.display = 'none';
    }
    
    return false;
}
